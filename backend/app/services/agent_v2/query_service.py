import copy
import uuid
from collections.abc import Iterator
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.schemas.query import (
    AgentWorkflowResponse,
    AgentWorkflowRunListResponse,
    RouteDecision,
    WorkflowTraceEvent,
)
from app.schemas.tools import ToolExecutionRequest
from app.services.agent_v2.graph import build_graph
from app.schemas.query import RetrievalResult
from app.services.agent.tool_service import execute_tool_request
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.agent_v2.run_store import (
    get_persisted_agent_v2_run,
    list_persisted_agent_v2_runs,
    persist_agent_v2_run,
)
from app.services.agent_v2.tracing import finalize_agent_v2_trace, trace_agent_v2_run


SKILL_CATALOG: dict[str, dict[str, Any]] = {
    "retrieve_grounded_knowledge": {
        "skill_label": "Retrieve Grounded Knowledge",
        "description": "Retrieve and ground an answer against indexed knowledge assets.",
        "owned_tools": ["document_search"],
        "workflow_families": ["knowledge_retrieval"],
    },
    "resolve_missing_context": {
        "skill_label": "Resolve Missing Context",
        "description": "Collect clarification data before the workflow can continue safely.",
        "owned_tools": [],
        "workflow_families": ["clarification", "incident_triage", "tool_execution"],
    },
    "execute_operational_tool": {
        "skill_label": "Execute Operational Tool",
        "description": "Execute a single operational tool request with structured tracing.",
        "owned_tools": ["system_status", "document_search", "ticketing"],
        "workflow_families": ["tool_execution"],
    },
    "review_service_health": {
        "skill_label": "Review Service Health",
        "description": "Inspect the target service health and normalize the runtime status snapshot.",
        "owned_tools": ["system_status"],
        "workflow_families": ["incident_triage", "service_runtime_review"],
    },
    "collect_runtime_guidance": {
        "skill_label": "Collect Runtime Guidance",
        "description": "Retrieve runbook guidance to recommend the next runtime checks for a service.",
        "owned_tools": ["document_search"],
        "workflow_families": ["service_runtime_review"],
    },
    "inspect_service_dependencies": {
        "skill_label": "Inspect Service Dependencies",
        "description": "Inspect structured dependency data to identify the most likely downstream dependency to check next.",
        "owned_tools": ["service_dependencies"],
        "workflow_families": ["service_runtime_review"],
    },
    "collect_incident_evidence": {
        "skill_label": "Collect Incident Evidence",
        "description": "Gather runbook and external evidence that supports incident diagnosis.",
        "owned_tools": ["document_search"],
        "workflow_families": ["incident_triage"],
    },
    "prepare_incident_ticket": {
        "skill_label": "Prepare Incident Ticket",
        "description": "Prepare, confirm, and submit incident tickets with explicit operator control.",
        "owned_tools": ["ticketing"],
        "workflow_families": ["incident_triage"],
    },
}


def _normalize_question(question: str) -> str:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question_must_not_be_empty")
    return normalized_question


def _normalize_top_k(top_k: int) -> int:
    if top_k <= 0:
        raise ValueError("top_k_must_be_positive")
    return top_k


def _build_initial_state(question: str, filename: str | None, top_k: int) -> dict[str, Any]:
    return {
        "question": question,
        "filename": filename or "",
        "top_k": top_k,
        "debug_fault_injection": {},
        "route": "",
        "route_reason": None,
        "route_planning_mode": None,
        "supervisor_agent": None,
        "supervisor_reason": None,
        "retrieval_result": None,
        "tool_chain": [],
        "clarification_question": None,
        "clarification_plan": None,
        "applied_clarification_fields": [],
        "question_rewritten": False,
        "answer": None,
        "answer_source": None,
        "model": None,
        "answered_at": None,
        "answer_latency_ms": None,
        "chat_provider": None,
        "chat_model": None,
        "workflow_status": "in_progress",
        "terminal_reason_override": None,
        "failure_stage": None,
        "retry_state": None,
        "retry_count": 0,
        "error": None,
        "messages": [],
    }


def _build_graph_invoke_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


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
                        }
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

    missing_fields = clarification_plan.get("missing_fields", []) if isinstance(clarification_plan, dict) else []
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


def _extract_interrupt_payload(final_state: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = final_state.get("__interrupt__")
    if not isinstance(interrupts, (list, tuple)) or not interrupts:
        return None

    interrupt_event = interrupts[0]
    payload = getattr(interrupt_event, "value", None)
    return payload if isinstance(payload, dict) else None


def _collect_tool_payload(final_state: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    tool_execution = None
    tool_plan = None
    tool_chain = final_state.get("tool_chain") or []
    if tool_chain:
        last_step = tool_chain[-1]
        if isinstance(last_step, dict):
            tool_plan = last_step.get("tool_plan")
            tool_execution = last_step.get("tool_execution")
    return tool_plan, tool_execution, tool_chain


def _build_skill_definition(skill_id: str) -> dict[str, Any]:
    definition = SKILL_CATALOG[skill_id]
    return {
        "skill_id": skill_id,
        "skill_label": definition["skill_label"],
        "description": definition["description"],
        "owned_tools": definition["owned_tools"],
        "workflow_families": definition["workflow_families"],
    }


def _resolve_workflow_family(final_state: dict[str, Any], interrupt_payload: dict[str, Any] | None) -> str:
    if interrupt_payload is not None:
        clarification_plan = final_state.get("clarification_plan")
        if isinstance(clarification_plan, dict) and clarification_plan.get("confirmation_kind") == "ticket_submission":
            return "incident_triage"
        return "clarification"

    if final_state.get("answer_source") == "local_incident_triage":
        return "incident_triage"
    if final_state.get("answer_source") == "local_service_runtime_review":
        return "service_runtime_review"

    route = final_state.get("route") or "knowledge_retrieval"
    if route == "tool_execution":
        return "tool_execution"
    if route == "clarification_needed":
        return "clarification"
    return "knowledge_retrieval"


def _resolve_step_skill_id(step: dict[str, Any], workflow_family: str) -> str:
    tool_plan = step.get("tool_plan") or {}
    tool_name = str(tool_plan.get("tool_name") or "").strip().lower()
    if workflow_family == "incident_triage":
        if tool_name == "system_status":
            return "review_service_health"
        if tool_name == "document_search":
            return "collect_incident_evidence"
        if tool_name == "ticketing":
            return "prepare_incident_ticket"
    if workflow_family == "service_runtime_review":
        if tool_name == "system_status":
            return "review_service_health"
        if tool_name == "service_dependencies":
            return "inspect_service_dependencies"
        if tool_name == "document_search":
            return "collect_runtime_guidance"
    if workflow_family == "knowledge_retrieval":
        return "retrieve_grounded_knowledge"
    if workflow_family == "clarification":
        return "resolve_missing_context"
    return "execute_operational_tool"


def _build_skill_summary(skill_id: str, steps: list[dict[str, Any]], workflow_family: str) -> str:
    if skill_id == "review_service_health":
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            summary = str(output.get("summary") or "").strip()
            if summary:
                return summary
        return "Reviewed the target service health."
    if skill_id == "collect_incident_evidence":
        matched_documents: list[str] = []
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            raw_documents = str(output.get("matched_documents") or "").strip()
            if raw_documents:
                matched_documents.extend(item.strip() for item in raw_documents.split(",") if item.strip())
        if matched_documents:
            unique_documents = list(dict.fromkeys(matched_documents))
            return f"Collected supporting evidence from {', '.join(unique_documents[:3])}."
        return "Collected supporting incident evidence."
    if skill_id == "collect_runtime_guidance":
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            matched_documents = str(output.get("matched_documents") or "").strip()
            if matched_documents:
                return f"Collected runtime guidance from {matched_documents}."
        return "Collected runtime guidance for the requested service."
    if skill_id == "inspect_service_dependencies":
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            primary_dependency = str(output.get("suspected_primary_dependency") or "").strip()
            if primary_dependency:
                return f"Identified {primary_dependency} as the most likely downstream dependency to inspect."
        return "Inspected the service dependency map."
    if skill_id == "prepare_incident_ticket":
        last_step = steps[-1] if steps else {}
        output = (last_step.get("tool_execution") or {}).get("output") or {}
        ticket_id = str(output.get("ticket_id") or "").strip()
        submission_state = str(output.get("submission_state") or output.get("status") or "").strip()
        if ticket_id and submission_state:
            return f"Ticket {ticket_id} is currently in state {submission_state}."
        if ticket_id:
            return f"Prepared ticket {ticket_id}."
        return "Prepared incident ticket workflow state."
    if skill_id == "retrieve_grounded_knowledge":
        return "Retrieved grounded knowledge for the requested question."
    if skill_id == "resolve_missing_context":
        return "Awaiting clarification before continuing workflow execution."
    if workflow_family == "tool_execution":
        return "Executed the planned operational tool sequence."
    return "Prepared reusable skill metadata for the workflow."


def _build_skill_metadata(
    final_state: dict[str, Any],
    interrupt_payload: dict[str, Any] | None,
    tool_chain: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    workflow_family = _resolve_workflow_family(final_state, interrupt_payload)
    enriched_tool_chain: list[dict[str, Any]] = []
    skill_steps: dict[str, list[dict[str, Any]]] = {}

    for step in tool_chain:
        if not isinstance(step, dict):
            continue
        skill_id = _resolve_step_skill_id(step, workflow_family)
        enriched_step = copy.deepcopy(step)
        enriched_step["skill_id"] = skill_id
        enriched_step["skill_label"] = SKILL_CATALOG[skill_id]["skill_label"]
        enriched_tool_chain.append(enriched_step)
        skill_steps.setdefault(skill_id, []).append(enriched_step)

    if not skill_steps:
        fallback_skill_id = (
            "resolve_missing_context"
            if workflow_family == "clarification"
            else "retrieve_grounded_knowledge"
            if workflow_family == "knowledge_retrieval"
            else "execute_operational_tool"
        )
        return workflow_family, enriched_tool_chain, [_build_skill_definition(fallback_skill_id)], [
            {
                "skill_id": fallback_skill_id,
                "skill_label": SKILL_CATALOG[fallback_skill_id]["skill_label"],
                "status": final_state.get("workflow_status") or "completed",
                "summary": _build_skill_summary(fallback_skill_id, [], workflow_family),
                "tool_names": SKILL_CATALOG[fallback_skill_id]["owned_tools"],
            }
        ]

    available_skills = [_build_skill_definition(skill_id) for skill_id in skill_steps]
    skill_trace = [
        {
            "skill_id": skill_id,
            "skill_label": SKILL_CATALOG[skill_id]["skill_label"],
            "status": final_state.get("workflow_status") or "completed",
            "summary": _build_skill_summary(skill_id, steps, workflow_family),
            "tool_names": list(dict.fromkeys(str((step.get("tool_plan") or {}).get("tool_name") or "") for step in steps if (step.get("tool_plan") or {}).get("tool_name"))),
        }
        for skill_id, steps in skill_steps.items()
    ]
    return workflow_family, enriched_tool_chain, available_skills, skill_trace


def _is_ticket_submission_confirmation_plan(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict):
        return False
    return str(plan.get("confirmation_kind") or "").strip().lower() == "ticket_submission"


def _interpret_ticket_submission_confirmation(clarification_context: dict[str, str] | None) -> bool | None:
    if not isinstance(clarification_context, dict):
        return None

    for key in ("submission_confirmation", "confirmation", "confirm", "submit_ticket", "approve"):
        raw_value = clarification_context.get(key)
        if not isinstance(raw_value, str):
            continue
        normalized = raw_value.strip().lower()
        if normalized in {"yes", "y", "true", "confirm", "confirmed", "submit", "approved"}:
            return True
        if normalized in {"no", "n", "false", "cancel", "decline", "declined", "reject", "rejected"}:
            return False
    return None


def _append_workflow_trace_event(
    events: list[WorkflowTraceEvent],
    *,
    stage: str,
    status: str,
    timestamp: str,
    detail: str,
) -> list[WorkflowTraceEvent]:
    return [
        *events,
        WorkflowTraceEvent(
            stage=stage,
            status=status,
            timestamp=timestamp,
            detail=detail,
        ),
    ]


def _resume_ticket_submission_confirmation(
    *,
    persisted_run: AgentWorkflowResponse,
    clarification_context: dict[str, str] | None,
) -> AgentWorkflowResponse:
    decision = _interpret_ticket_submission_confirmation(clarification_context)
    if decision is None:
        raise ValueError("ticket_submission_confirmation_required")

    clarification_plan = persisted_run.clarification_plan or {}
    ticket_id = str(clarification_plan.get("ticket_id") or "").strip()
    if not ticket_id:
        raise ValueError("ticket_submission_ticket_id_missing")

    timestamp = build_utc_timestamp()
    applied_fields = sorted(
        key
        for key, value in (clarification_context or {}).items()
        if isinstance(value, str) and value.strip()
    )

    if not decision:
        answer = f"Left ticket draft {ticket_id} unsubmitted at operator request."
        response = persisted_run.model_copy(
            update={
                "workflow_status": "completed",
                "terminal_reason": "ticket_submission_cancelled",
                "outcome_category": "completed",
                "is_recoverable": None,
                "recommended_recovery_action": "none",
                "available_recovery_actions": [],
                "recovery_action_details": {},
                "answer": answer,
                "answer_source": "local_incident_triage",
                "answered_at": timestamp,
                "completed_at": timestamp,
                "last_updated_at": timestamp,
                "clarification_message": None,
                "clarification_plan": None,
                "applied_clarification_fields": applied_fields,
                "workflow_trace": _append_workflow_trace_event(
                    persisted_run.workflow_trace,
                    stage="clarification",
                    status="completed",
                    timestamp=timestamp,
                    detail=answer,
                ),
            }
        )
        persist_agent_v2_run(response)
        return response

    last_tool_execution = persisted_run.tool_execution or {}
    draft_target = str(last_tool_execution.get("target") or "").strip()
    if not draft_target:
        draft_target = str((persisted_run.tool_plan or {}).get("target") or "").strip()
    if not draft_target:
        raise ValueError("ticket_submission_target_missing")

    submit_execution = execute_tool_request(
        ToolExecutionRequest(
            tool_name="ticketing",
            action="submit",
            target=draft_target,
            arguments={"ticket_id": ticket_id},
        )
    )
    submit_step = {
        "step_id": f"step_{len(persisted_run.tool_chain) + 1}",
        "step_index": len(persisted_run.tool_chain) + 1,
        "step_status": submit_execution.execution_status,
        "attempt_count": 1,
        "retried": False,
        "started_at": timestamp,
        "completed_at": submit_execution.executed_at,
        "question": persisted_run.question,
        "tool_plan": {
            "question": persisted_run.question,
            "planning_mode": "agent_v2_incident_triage_resume",
            "route_hint": "tool_execution",
            "tool_name": "ticketing",
            "action": "submit",
            "target": draft_target,
            "arguments": {"ticket_id": ticket_id},
            "plan_summary": f"Plan ticketing:submit for {draft_target}.",
        },
        "tool_execution": submit_execution.model_dump(),
        "failure_message": None,
    }
    answer = (
        f"Incident triage submitted ticket {ticket_id} for {draft_target} after operator confirmation."
    )
    response = persisted_run.model_copy(
        update={
            "workflow_status": "completed",
            "terminal_reason": "ticket_submitted",
            "outcome_category": "completed",
            "is_recoverable": None,
            "recommended_recovery_action": "none",
            "available_recovery_actions": [],
            "recovery_action_details": {},
            "answer": answer,
            "answer_source": "local_incident_triage",
            "answered_at": timestamp,
            "completed_at": timestamp,
            "last_updated_at": timestamp,
            "clarification_message": None,
            "clarification_plan": None,
            "tool_plan": submit_step["tool_plan"],
            "tool_execution": submit_step["tool_execution"],
            "tool_chain": [*persisted_run.tool_chain, submit_step],
            "step_count": len(persisted_run.tool_chain) + 1,
            "applied_clarification_fields": applied_fields,
            "workflow_trace": _append_workflow_trace_event(
                _append_workflow_trace_event(
                    persisted_run.workflow_trace,
                    stage="clarification",
                    status="completed",
                    timestamp=timestamp,
                    detail=f"Operator confirmed submission of draft {ticket_id}.",
                ),
                stage="tool_execution",
                status="completed",
                timestamp=timestamp,
                detail=answer,
            ),
        }
    )
    persist_agent_v2_run(response)
    return response


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
        terminal_reason=_resolve_terminal_reason(
            final_state=final_state,
            interrupt_payload=interrupt_payload,
        ),
        outcome_category=workflow_status,
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


def _merge_stream_update(
    accumulated_state: dict[str, Any],
    update: dict[str, Any],
) -> dict[str, Any]:
    merged_state = copy.deepcopy(accumulated_state)
    for value in update.values():
        if isinstance(value, dict):
            merged_state.update(value)
        else:
            merged_state["__interrupt__"] = value
    return merged_state


def _build_stream_event(
    *,
    event_type: str,
    stage: str,
    status: str,
    detail: str,
    timestamp: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "stage": stage,
        "status": status,
        "detail": detail,
        "timestamp": timestamp,
        "payload": payload or {},
    }


def _translate_stream_update_to_event(
    update: dict[str, Any],
    *,
    timestamp: str,
) -> dict[str, Any] | None:
    if "router" in update:
        payload = update["router"]
        route = payload.get("route") or "unknown"
        return _build_stream_event(
            event_type="node_update",
            stage="routing",
            status=payload.get("workflow_status") or "in_progress",
            detail=f"Route selected: {route}. {payload.get('route_reason') or 'No route reason provided.'}",
            timestamp=timestamp,
            payload=payload,
        )

    if "retrieval" in update:
        payload = update["retrieval"]
        retrieval_result = payload.get("retrieval_result") or {}
        matches = retrieval_result.get("matches") or []
        return _build_stream_event(
            event_type="node_update",
            stage="retrieval",
            status=payload.get("workflow_status") or "in_progress",
            detail=f"Retrieved {len(matches)} supporting chunk(s) and prepared an answer draft.",
            timestamp=timestamp,
            payload={
                "match_count": len(matches),
                "answer_source": payload.get("answer_source"),
            },
        )

    if "supervisor" in update:
        payload = update["supervisor"]
        specialist = payload.get("supervisor_agent") or "unknown_specialist"
        return _build_stream_event(
            event_type="node_update",
            stage="supervisor",
            status=payload.get("workflow_status") or "in_progress",
            detail=payload.get("supervisor_reason")
            or f"Supervisor delegated to {specialist}.",
            timestamp=timestamp,
            payload={
                "supervisor_agent": specialist,
            },
        )

    if "knowledge_specialist" in update:
        payload = update["knowledge_specialist"]
        retrieval_result = payload.get("retrieval_result") or {}
        matches = retrieval_result.get("matches") or []
        return _build_stream_event(
            event_type="node_update",
            stage="knowledge_specialist",
            status=payload.get("workflow_status") or "in_progress",
            detail=f"Knowledge specialist retrieved {len(matches)} supporting chunk(s).",
            timestamp=timestamp,
            payload={"match_count": len(matches)},
        )

    if "operations_specialist" in update:
        payload = update["operations_specialist"]
        tool_chain = payload.get("tool_chain") or []
        last_step = tool_chain[-1] if tool_chain else {}
        tool_execution = last_step.get("tool_execution") if isinstance(last_step, dict) else {}
        result_summary = tool_execution.get("result_summary") or "Operations specialist completed tool execution."
        return _build_stream_event(
            event_type="node_update",
            stage="operations_specialist",
            status=payload.get("workflow_status") or "completed",
            detail=result_summary,
            timestamp=timestamp,
            payload={
                "tool_name": tool_execution.get("tool_name"),
                "execution_status": tool_execution.get("execution_status"),
            },
        )

    if "clarification_specialist" in update:
        payload = update["clarification_specialist"]
        return _build_stream_event(
            event_type="node_update",
            stage="clarification_specialist",
            status=payload.get("workflow_status") or "in_progress",
            detail=payload.get("clarification_question") or "Clarification specialist resumed the workflow.",
            timestamp=timestamp,
            payload={
                "question_rewritten": bool(payload.get("question_rewritten")),
            },
        )

    if "tool_exec" in update:
        payload = update["tool_exec"]
        tool_chain = payload.get("tool_chain") or []
        last_step = tool_chain[-1] if tool_chain else {}
        tool_plan = last_step.get("tool_plan") if isinstance(last_step, dict) else {}
        tool_execution = last_step.get("tool_execution") if isinstance(last_step, dict) else {}
        tool_name = tool_plan.get("tool_name") or tool_execution.get("tool_name") or "tool"
        result_summary = tool_execution.get("result_summary") or "Tool execution completed."
        return _build_stream_event(
            event_type="node_update",
            stage="tool_execution",
            status=payload.get("workflow_status") or "completed",
            detail=result_summary,
            timestamp=timestamp,
            payload={
                "tool_name": tool_name,
                "execution_status": tool_execution.get("execution_status"),
            },
        )

    if "answer" in update:
        payload = update["answer"]
        return _build_stream_event(
            event_type="node_update",
            stage="answer",
            status=payload.get("workflow_status") or "completed",
            detail=payload.get("answer") or "Answer generated.",
            timestamp=timestamp,
            payload={
                "answer_source": payload.get("answer_source"),
            },
        )

    if "__interrupt__" in update:
        interrupt_payload = _extract_interrupt_payload({"__interrupt__": update["__interrupt__"]}) or {}
        return _build_stream_event(
            event_type="interrupt",
            stage="clarification",
            status="clarification_required",
            detail=interrupt_payload.get("clarification_question") or "Clarification requested.",
            timestamp=timestamp,
            payload=interrupt_payload,
        )

    return None


def _execute_agent_v2_workflow(
    *,
    run_id: str,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
    debug_fault_injection: dict[str, Any] | None = None,
    root_run_id: str | None = None,
    recovery_depth: int = 0,
    source_run_id: str | None = None,
    recovered_via_action: str | None = None,
    resume_source_type: str | None = None,
    resume_strategy: str | None = None,
    resumed_from_step_index: int | None = None,
    reused_step_indices: list[int] | None = None,
    retried_step_indices: list[int] | None = None,
) -> AgentWorkflowResponse:
    normalized_question = _normalize_question(question)
    normalized_filename = filename.strip() if isinstance(filename, str) else None
    top_k = _normalize_top_k(top_k)

    graph = build_graph(checkpointer=checkpointer or InMemorySaver())
    initial_state = _build_initial_state(
        question=normalized_question,
        filename=normalized_filename,
        top_k=top_k,
    )
    initial_state["debug_fault_injection"] = debug_fault_injection or {}
    invoke_config = _build_graph_invoke_config(run_id)

    with trace_agent_v2_run(
        operation="orchestrate",
        inputs={
            "run_id": run_id,
            "question": normalized_question,
            "filename": normalized_filename,
            "top_k": top_k,
        },
        metadata={
            "has_checkpointer": checkpointer is not None,
        },
    ) as trace_run:
        try:
            final_state = graph.invoke(initial_state, config=invoke_config)
            timestamp = build_utc_timestamp()
            response = _build_agent_v2_response(
                run_id=run_id,
                question=normalized_question,
                filename=normalized_filename,
                final_state=final_state,
                started_at=timestamp,
                completed_at=timestamp,
                last_updated_at=timestamp,
            )
            response.root_run_id = root_run_id
            response.recovery_depth = recovery_depth
            response.source_run_id = source_run_id
            response.recovered_via_action = recovered_via_action
            response.resume_source_type = resume_source_type
            response.resume_strategy = resume_strategy
            response.resumed_from_step_index = resumed_from_step_index
            response.reused_step_indices = reused_step_indices or []
            response.retried_step_indices = retried_step_indices or []
            persist_agent_v2_run(response)
            finalize_agent_v2_trace(trace_run, response=response)
            return response
        except Exception as exc:
            finalize_agent_v2_trace(trace_run, error=exc)
            raise


def orchestrate_agent_v2_request(
    *,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
    debug_fault_injection: dict[str, Any] | None = None,
) -> AgentWorkflowResponse:
    return _execute_agent_v2_workflow(
        run_id=uuid.uuid4().hex,
        question=question,
        filename=filename,
        top_k=top_k,
        checkpointer=checkpointer,
        debug_fault_injection=debug_fault_injection,
    )


def stream_agent_v2_request(
    *,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
    debug_fault_injection: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    normalized_question = _normalize_question(question)
    normalized_filename = filename.strip() if isinstance(filename, str) else None
    top_k = _normalize_top_k(top_k)
    graph = build_graph(checkpointer=checkpointer or InMemorySaver())
    initial_state = _build_initial_state(
        question=normalized_question,
        filename=normalized_filename,
        top_k=top_k,
    )
    initial_state["debug_fault_injection"] = debug_fault_injection or {}
    run_id = uuid.uuid4().hex
    invoke_config = _build_graph_invoke_config(run_id)
    accumulated_state = copy.deepcopy(initial_state)
    started_at = build_utc_timestamp()

    yield _build_stream_event(
        event_type="status",
        stage="start",
        status="in_progress",
        detail="Agent workflow started.",
        timestamp=started_at,
        payload={
            "run_id": run_id,
            "question": normalized_question,
            "filename": normalized_filename,
            "top_k": top_k,
        },
    )

    with trace_agent_v2_run(
        operation="stream",
        inputs={
            "run_id": run_id,
            "question": normalized_question,
            "filename": normalized_filename,
            "top_k": top_k,
        },
        metadata={
            "has_checkpointer": checkpointer is not None,
        },
    ) as trace_run:
        try:
            for update in graph.stream(initial_state, config=invoke_config, stream_mode="updates"):
                accumulated_state = _merge_stream_update(accumulated_state, update)
                event = _translate_stream_update_to_event(update, timestamp=build_utc_timestamp())
                if event is not None:
                    yield event

            completed_at = build_utc_timestamp()
            response = _build_agent_v2_response(
                run_id=run_id,
                question=normalized_question,
                filename=normalized_filename,
                final_state=accumulated_state,
                started_at=started_at,
                completed_at=completed_at,
                last_updated_at=completed_at,
            )
            persist_agent_v2_run(response)
            finalize_agent_v2_trace(trace_run, response=response)

            yield _build_stream_event(
                event_type="status",
                stage="workflow",
                status=response.workflow_status,
                detail=response.terminal_reason or "Workflow completed.",
                timestamp=completed_at,
                payload={
                    "run_id": response.run_id,
                    "workflow_status": response.workflow_status,
                    "terminal_reason": response.terminal_reason,
                },
            )
            yield {
                "event_type": "result",
                "response": response.model_dump(mode="json"),
            }
        except Exception as exc:
            finalize_agent_v2_trace(trace_run, error=exc)
            yield _build_stream_event(
                event_type="error",
                stage="workflow",
                status="failed",
                detail=str(exc),
                timestamp=build_utc_timestamp(),
                payload={},
            )


def resume_agent_v2_request(
    *,
    run_id: str,
    clarification_context: dict[str, str] | None = None,
    checkpointer=None,
) -> AgentWorkflowResponse:
    persisted_run = get_persisted_agent_v2_run(run_id)
    if _is_ticket_submission_confirmation_plan(persisted_run.clarification_plan):
        return _resume_ticket_submission_confirmation(
            persisted_run=persisted_run,
            clarification_context=clarification_context,
        )

    if checkpointer is None:
        return persisted_run

    graph = build_graph(checkpointer=checkpointer)
    invoke_config = _build_graph_invoke_config(run_id)
    snapshot = graph.get_state(invoke_config)
    if not snapshot.values:
        return persisted_run

    with trace_agent_v2_run(
        operation="resume",
        inputs={
            "run_id": run_id,
            "clarification_context_keys": sorted((clarification_context or {}).keys()),
        },
        metadata={
            "original_workflow_status": persisted_run.workflow_status,
            "original_route_type": persisted_run.route.route_type,
        },
    ) as trace_run:
        try:
            if clarification_context:
                resumed_state = graph.invoke(Command(resume=clarification_context), config=invoke_config)
            else:
                resumed_state = graph.invoke(None, config=invoke_config)
            timestamp = build_utc_timestamp()
            interrupt_payload = _extract_interrupt_payload(resumed_state)
            route_type = resumed_state.get("route") or persisted_run.route.route_type
            route_reason = resumed_state.get("route_reason") or persisted_run.route.route_reason
            answer = resumed_state.get("answer") or persisted_run.answer
            answer_source = resumed_state.get("answer_source") or persisted_run.answer_source
            retrieval_payload = resumed_state.get("retrieval_result")
            retrieval = RetrievalResult.model_validate(retrieval_payload) if retrieval_payload else persisted_run.retrieval
            tool_chain = resumed_state.get("tool_chain") or persisted_run.tool_chain
            tool_execution = persisted_run.tool_execution
            tool_plan = persisted_run.tool_plan
            if tool_chain:
                last_step = tool_chain[-1]
                if isinstance(last_step, dict):
                    tool_plan = last_step.get("tool_plan") or tool_plan
                    tool_execution = last_step.get("tool_execution") or tool_execution

            workflow_status = resumed_state.get("workflow_status") or persisted_run.workflow_status
            clarification_question = resumed_state.get("clarification_question") or persisted_run.clarification_message
            clarification_plan = resumed_state.get("clarification_plan") or persisted_run.clarification_plan
            if interrupt_payload is not None:
                workflow_status = "clarification_required"
                route_type = "clarification_needed"
                clarification_question = interrupt_payload.get("clarification_question")
                clarification_plan = interrupt_payload.get("clarification_plan")
                answer = None
                answer_source = None
                retrieval = None

            recovery_metadata = _build_recovery_metadata(
                workflow_status=workflow_status,
                clarification_plan=clarification_plan,
                route_type=route_type,
                tool_chain=tool_chain,
            )

            response = AgentWorkflowResponse(
                run_id=persisted_run.run_id,
                root_run_id=persisted_run.root_run_id,
                recovery_depth=persisted_run.recovery_depth,
                question=resumed_state.get("question") or persisted_run.question,
                resumed_from_question=persisted_run.resumed_from_question,
                source_run_id=persisted_run.source_run_id,
                recovered_via_action=persisted_run.recovered_via_action,
                resume_source_type="run_id",
                resume_strategy="checkpoint_resume",
                resumed_from_step_index=persisted_run.resumed_from_step_index,
                reused_step_indices=persisted_run.reused_step_indices,
                overridden_plan_arguments=persisted_run.overridden_plan_arguments,
                workflow_status=workflow_status,
                terminal_reason=_resolve_terminal_reason(
                    final_state=resumed_state,
                    interrupt_payload=interrupt_payload,
                ),
                outcome_category=resumed_state.get("workflow_status") or persisted_run.outcome_category,
                is_recoverable=recovery_metadata["is_recoverable"],
                retry_state=resumed_state.get("retry_state") or persisted_run.retry_state,
                recommended_recovery_action=recovery_metadata["recommended_recovery_action"],
                available_recovery_actions=recovery_metadata["available_recovery_actions"],
                recovery_action_details=recovery_metadata["recovery_action_details"],
                failure_stage=resumed_state.get("failure_stage") or persisted_run.failure_stage,
                failure_message=resumed_state.get("error") or persisted_run.failure_message,
                started_at=persisted_run.started_at,
                completed_at=_resolve_resumed_completed_at(
                    persisted_run=persisted_run,
                    resumed_state=resumed_state,
                    timestamp=timestamp,
                ),
                last_updated_at=timestamp,
                workflow_planning_mode=resumed_state.get("route_planning_mode") or persisted_run.workflow_planning_mode,
                tool_planning_mode=persisted_run.tool_planning_mode,
                tool_planning_modes=persisted_run.tool_planning_modes,
                clarification_planning_mode=persisted_run.clarification_planning_mode,
                planner_call_count=persisted_run.planner_call_count,
                tool_planner_call_count=persisted_run.tool_planner_call_count,
                workflow_planning_latency_ms=persisted_run.workflow_planning_latency_ms,
                tool_planning_latency_ms=persisted_run.tool_planning_latency_ms,
                clarification_planning_latency_ms=persisted_run.clarification_planning_latency_ms,
                planner_latency_ms_total=persisted_run.planner_latency_ms_total,
                llm_planner_layers=persisted_run.llm_planner_layers,
                fallback_planner_layers=persisted_run.fallback_planner_layers,
                llm_tool_planner_steps=persisted_run.llm_tool_planner_steps,
                fallback_tool_planner_steps=persisted_run.fallback_tool_planner_steps,
                retry_count=int(resumed_state.get("retry_count") or persisted_run.retry_count),
                retried_step_indices=persisted_run.retried_step_indices,
                step_count=len(tool_chain),
                route=RouteDecision(
                    route_type=route_type,
                    route_reason=route_reason,
                    filename=resumed_state.get("filename") or persisted_run.filename,
                ),
                workflow_trace=_build_workflow_trace(
                    resumed_state,
                    timestamp=timestamp,
                    answer_detail=answer,
                    clarification_detail=clarification_question,
                ),
                filename=resumed_state.get("filename") or persisted_run.filename,
                answer=answer,
                answer_source=answer_source,
                model=resumed_state.get("model") or persisted_run.model,
                answered_at=resumed_state.get("answered_at") or persisted_run.answered_at,
                answer_latency_ms=resumed_state.get("answer_latency_ms") or persisted_run.answer_latency_ms,
                chat_provider=resumed_state.get("chat_provider") or persisted_run.chat_provider,
                chat_model=resumed_state.get("chat_model") or persisted_run.chat_model,
                retrieval=retrieval,
                clarification_message=clarification_question,
                clarification_plan=clarification_plan,
                tool_plan=tool_plan,
                tool_execution=tool_execution,
                tool_chain=tool_chain,
                applied_clarification_fields=resumed_state.get("applied_clarification_fields") or persisted_run.applied_clarification_fields,
                question_rewritten=bool(resumed_state.get("question_rewritten") or persisted_run.question_rewritten),
            )
            persist_agent_v2_run(response)
            finalize_agent_v2_trace(trace_run, response=response)
            return response
        except Exception as exc:
            finalize_agent_v2_trace(trace_run, error=exc)
            raise


def list_agent_v2_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    return list_persisted_agent_v2_runs(limit=limit)


def recover_agent_v2_request(
    *,
    run_id: str,
    recovery_action: str | None,
    clarification_context: dict[str, str] | None = None,
    checkpointer=None,
    debug_fault_injection: dict[str, Any] | None = None,
) -> AgentWorkflowResponse:
    selected_action = (recovery_action or "").strip() or "manual_retrigger"
    if selected_action == "resume_with_clarification":
        response = resume_agent_v2_request(
            run_id=run_id,
            clarification_context=clarification_context,
            checkpointer=checkpointer,
        )
        response.recovered_via_action = selected_action
        response.resume_source_type = "run_id"
        response.resume_strategy = "clarification_recovery"
        persist_agent_v2_run(response)
        return response
    if selected_action not in {"manual_retrigger", "resume_from_failed_step"}:
        raise ValueError("recovery_action_not_supported_for_agent_v2")

    source_run = get_persisted_agent_v2_run(run_id)
    if source_run.workflow_status != "failed":
        raise ValueError(f"{selected_action}_requires_failed_run")

    top_k = source_run.retrieval.top_k if source_run.retrieval is not None else 3
    failed_step_index = None
    if source_run.tool_chain:
        failed_step_index = source_run.tool_chain[-1].step_index
    return _execute_agent_v2_workflow(
        run_id=uuid.uuid4().hex,
        question=source_run.question,
        filename=source_run.filename,
        top_k=top_k,
        checkpointer=checkpointer,
        debug_fault_injection=debug_fault_injection,
        root_run_id=source_run.root_run_id or source_run.run_id,
        recovery_depth=(source_run.recovery_depth or 0) + 1,
        source_run_id=source_run.run_id,
        recovered_via_action=selected_action,
        resume_source_type="run_id",
        resume_strategy=(
            "failed_step_resume"
            if selected_action == "resume_from_failed_step"
            else "manual_retrigger_recovery"
        ),
        resumed_from_step_index=failed_step_index if selected_action == "resume_from_failed_step" else None,
        reused_step_indices=[],
        retried_step_indices=[failed_step_index] if selected_action == "resume_from_failed_step" and failed_step_index is not None else [],
    )
