from typing import Any

from app.schemas.query import AgentWorkflowResponse, WorkflowTraceEvent
from app.schemas.tools import ToolExecutionRequest
from app.services.agent.tool_service import execute_tool_request
from app.services.agent_v2.run_store import persist_agent_v2_run
from app.services.agent_v2.workflow_policy import _interpret_ticket_submission_confirmation
from app.services.ingestion.document_service import build_utc_timestamp


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
                "workflow_outcome": "ticket_submission_cancelled",
                "recommended_next_actions": ["review_ticket_artifact"],
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
            "workflow_outcome": "ticket_submitted",
            "recommended_next_actions": [],
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
