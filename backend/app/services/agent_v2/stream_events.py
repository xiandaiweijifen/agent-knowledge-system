import copy
import uuid
from typing import Any

from app.services.agent_v2.tool_extraction import _extract_interrupt_payload


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
            detail=payload.get("supervisor_reason") or f"Supervisor delegated to {specialist}.",
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
        result_summary = (
            tool_execution.get("result_summary") or "Operations specialist completed tool execution."
        )
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
            detail=payload.get("clarification_question")
            or "Clarification specialist resumed the workflow.",
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
        interrupt_payload = (
            _extract_interrupt_payload({"__interrupt__": update["__interrupt__"]}) or {}
        )
        return _build_stream_event(
            event_type="interrupt",
            stage="clarification",
            status="clarification_required",
            detail=interrupt_payload.get("clarification_question") or "Clarification requested.",
            timestamp=timestamp,
            payload=interrupt_payload,
        )

    return None
