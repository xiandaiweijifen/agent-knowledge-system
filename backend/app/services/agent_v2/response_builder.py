from typing import Any

from app.schemas.query import (
    AgentWorkflowResponse,
    RetrievalResult,
    RouteDecision,
    WorkflowTraceEvent,
)
from app.services.agent_v2.skill_catalog import _build_skill_metadata
from app.services.agent_v2.tool_extraction import (
    _collect_tool_payload,
    _extract_interrupt_payload,
)
from app.services.agent_v2.workflow_policy import _build_workflow_policy


def _build_terminal_reason(final_state: dict[str, Any]) -> str:
    terminal_reason_override = final_state.get("terminal_reason_override")
    if isinstance(terminal_reason_override, str) and terminal_reason_override.strip():
        return terminal_reason_override

    workflow_status = final_state.get("workflow_status")
    if workflow_status == "failed":
        failure_stage = final_state.get("failure_stage")
        if failure_stage == "tool_execution":
            return "tool_execution_failed"
        if failure_stage == "knowledge_retrieval":
            return "knowledge_retrieval_failed"
        return "agent_v2_failed"
    if workflow_status == "clarification_required":
        return "clarification_requested"
    if final_state.get("route") == "tool_execution":
        return "tool_execution_completed"
    if final_state.get("route") == "knowledge_retrieval":
        return "knowledge_answer_generated"
    return "agent_v2_completed"


def _resolve_terminal_reason(
    *,
    final_state: dict[str, Any],
    interrupt_payload: dict[str, Any] | None,
) -> str:
    if interrupt_payload is not None:
        return "clarification_requested"
    return _build_terminal_reason(final_state)


def _resolve_resumed_completed_at(
    *,
    persisted_run: AgentWorkflowResponse,
    resumed_state: dict[str, Any],
    timestamp: str,
) -> str | None:
    if persisted_run.completed_at:
        return persisted_run.completed_at

    resumed_workflow_status = resumed_state.get("workflow_status") or persisted_run.workflow_status
    if resumed_workflow_status == "completed":
        return timestamp

    return None


def _build_workflow_trace(
    final_state: dict[str, Any],
    *,
    timestamp: str,
    answer_detail: str | None = None,
    clarification_detail: str | None = None,
) -> list[WorkflowTraceEvent]:
    route = final_state.get("route") or "knowledge_retrieval"
    route_reason = final_state.get("route_reason") or "No route reason provided."
    workflow_status = final_state.get("workflow_status") or "completed"

    events = [
        WorkflowTraceEvent(
            stage="routing",
            status="completed",
            timestamp=timestamp,
            detail=f"Route selected: {route}. {route_reason}",
        )
    ]

    if final_state.get("supervisor_agent"):
        events.append(
            WorkflowTraceEvent(
                stage="supervisor",
                status="completed",
                timestamp=timestamp,
                detail=final_state.get("supervisor_reason")
                or f"Supervisor delegated to {final_state.get('supervisor_agent')}.",
            )
        )

    if workflow_status == "failed":
        events.append(
            WorkflowTraceEvent(
                stage=final_state.get("failure_stage") or "workflow",
                status="failed",
                timestamp=timestamp,
                detail=final_state.get("error") or "Workflow failed in agent_v2.",
            )
        )
    elif workflow_status == "clarification_required":
        events.append(
            WorkflowTraceEvent(
                stage="clarification",
                status=workflow_status,
                timestamp=timestamp,
                detail=clarification_detail
                or final_state.get("clarification_question")
                or "Clarification requested.",
            )
        )
    elif route == "tool_execution":
        if final_state.get("answer_source") == "local_incident_triage":
            tool_chain = final_state.get("tool_chain") or []
            if len(tool_chain) > 1:
                detail = answer_detail or "Incident triage workflow completed in agent_v2."
            else:
                detail = answer_detail or "Incident triage status check completed in agent_v2."
        elif final_state.get("answer_source") == "local_service_runtime_review":
            detail = answer_detail or "Service runtime review workflow completed in agent_v2."
        else:
            detail = "Tool execution node completed in agent_v2."
        events.append(
            WorkflowTraceEvent(
                stage="tool_execution",
                status=workflow_status,
                timestamp=timestamp,
                detail=detail,
            )
        )
    else:
        events.append(
            WorkflowTraceEvent(
                stage="answer",
                status=workflow_status,
                timestamp=timestamp,
                detail=answer_detail or final_state.get("answer") or "Answer generated in agent_v2.",
            )
        )

    return events


def _build_recovery_metadata(
    *,
    workflow_status: str,
    clarification_plan: dict[str, Any] | None,
    route_type: str | None = None,
    tool_chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if workflow_status != "clarification_required":
        if workflow_status == "failed":
            if route_type == "tool_execution":
                failed_step_index = None
                if tool_chain:
                    last_step = tool_chain[-1]
                    if isinstance(last_step, dict):
                        failed_step_index = last_step.get("step_index")
                return {
                    "recommended_recovery_action": "resume_from_failed_step",
                    "available_recovery_actions": ["resume_from_failed_step", "manual_retrigger"],
                    "recovery_action_details": {
                        "resume_from_failed_step": {
                            "failed_step_index": failed_step_index,
                            "strategy": "resume_single_failed_step",
                        },
                        "manual_retrigger": {
                            "strategy": "restart_workflow_from_beginning",
                        },
                    },
                    "is_recoverable": True,
                }
            return {
                "recommended_recovery_action": "manual_investigation",
                "available_recovery_actions": ["manual_investigation"],
                "recovery_action_details": {
                    "manual_investigation": {
                        "reason": "workflow_requires_manual_investigation",
                    }
                },
                "is_recoverable": False,
            }
        return {
            "recommended_recovery_action": "none",
            "available_recovery_actions": [],
            "recovery_action_details": {},
            "is_recoverable": None,
        }

    missing_fields = (
        clarification_plan.get("missing_fields", []) if isinstance(clarification_plan, dict) else []
    )
    return {
        "recommended_recovery_action": "resume_with_clarification",
        "available_recovery_actions": ["resume_with_clarification"],
        "recovery_action_details": {
            "resume_with_clarification": {
                "missing_fields": missing_fields,
            }
        },
        "is_recoverable": True,
    }


def _build_agent_v2_response(
    *,
    run_id: str,
    question: str,
    filename: str | None,
    final_state: dict[str, Any],
    started_at: str,
    completed_at: str,
    last_updated_at: str,
) -> AgentWorkflowResponse:
    interrupt_payload = _extract_interrupt_payload(final_state)
    route_type = final_state.get("route") or "knowledge_retrieval"
    route_reason = final_state.get("route_reason") or "Route selected by agent_v2."
    answer = final_state.get("answer")
    answer_source = final_state.get("answer_source")
    model = final_state.get("model")
    answered_at = final_state.get("answered_at") or (completed_at if answer else None)
    answer_latency_ms = final_state.get("answer_latency_ms")
    chat_provider = final_state.get("chat_provider")
    chat_model = final_state.get("chat_model")
    retrieval_payload = final_state.get("retrieval_result")
    retrieval = RetrievalResult.model_validate(retrieval_payload) if retrieval_payload else None
    tool_plan, tool_execution, raw_tool_chain = _collect_tool_payload(final_state)
    clarification_question = final_state.get("clarification_question")
    clarification_plan = final_state.get("clarification_plan")
    workflow_status = final_state.get("workflow_status") or "completed"

    if interrupt_payload is not None:
        workflow_status = "clarification_required"
        route_type = "clarification_needed"
        clarification_question = interrupt_payload.get("clarification_question")
        clarification_plan = interrupt_payload.get("clarification_plan")
        answer = None
        answer_source = None
        retrieval = None

    workflow_family, tool_chain, available_skills, skill_trace = _build_skill_metadata(
        final_state,
        interrupt_payload,
        raw_tool_chain,
    )
    terminal_reason = _resolve_terminal_reason(
        final_state=final_state,
        interrupt_payload=interrupt_payload,
    )
    workflow_outcome, recommended_next_actions = _build_workflow_policy(
        workflow_family=workflow_family,
        workflow_status=workflow_status,
        terminal_reason=terminal_reason,
        tool_chain=tool_chain,
    )
    recovery_metadata = _build_recovery_metadata(
        workflow_status=workflow_status,
        clarification_plan=clarification_plan,
        route_type=route_type,
        tool_chain=tool_chain,
    )

    return AgentWorkflowResponse(
        run_id=run_id,
        root_run_id=None,
        recovery_depth=0,
        question=question,
        workflow_status=workflow_status,
        terminal_reason=terminal_reason,
        outcome_category=workflow_status,
        workflow_outcome=workflow_outcome,
        recommended_next_actions=recommended_next_actions,
        is_recoverable=recovery_metadata["is_recoverable"],
        retry_state=final_state.get("retry_state"),
        recommended_recovery_action=recovery_metadata["recommended_recovery_action"],
        available_recovery_actions=recovery_metadata["available_recovery_actions"],
        recovery_action_details=recovery_metadata["recovery_action_details"],
        failure_stage=final_state.get("failure_stage"),
        failure_message=final_state.get("error"),
        started_at=started_at,
        completed_at=completed_at,
        last_updated_at=last_updated_at,
        workflow_planning_mode=final_state.get("route_planning_mode"),
        route=RouteDecision(
            route_type=route_type,
            route_reason=route_reason,
            filename=filename,
        ),
        workflow_trace=_build_workflow_trace(
            final_state,
            timestamp=last_updated_at,
            answer_detail=answer,
            clarification_detail=clarification_question,
        ),
        filename=filename,
        answer=answer,
        answer_source=answer_source,
        model=model,
        answered_at=answered_at,
        answer_latency_ms=answer_latency_ms,
        chat_provider=chat_provider,
        chat_model=chat_model,
        workflow_family=workflow_family,
        available_skills=available_skills,
        skill_trace=skill_trace,
        retrieval=retrieval,
        clarification_message=clarification_question,
        clarification_plan=clarification_plan,
        tool_plan=tool_plan,
        tool_execution=tool_execution,
        tool_chain=tool_chain,
        retry_count=int(final_state.get("retry_count") or 0),
        step_count=len(tool_chain),
        applied_clarification_fields=final_state.get("applied_clarification_fields") or [],
        question_rewritten=bool(final_state.get("question_rewritten")),
    )
