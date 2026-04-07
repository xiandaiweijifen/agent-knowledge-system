import uuid
from typing import Any

from app.schemas.query import AgentWorkflowResponse, RouteDecision, WorkflowTraceEvent
from app.services.agent.query_service import run_query
from app.services.agent_v2.graph import agent_graph, build_graph
from app.services.ingestion.document_service import build_utc_timestamp


def _build_initial_state(question: str, filename: str | None, top_k: int) -> dict[str, Any]:
    return {
        "question": question,
        "filename": filename or "",
        "top_k": top_k,
        "route": "",
        "route_reason": None,
        "route_planning_mode": None,
        "retrieval_result": None,
        "tool_chain": [],
        "clarification_question": None,
        "answer": None,
        "answer_source": None,
        "workflow_status": "in_progress",
        "error": None,
        "messages": [],
    }


def _build_graph_invoke_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "agent_v2",
        }
    }


def _build_terminal_reason(final_state: dict[str, Any]) -> str:
    workflow_status = final_state.get("workflow_status")
    if workflow_status == "clarification_required":
        return "clarification_requested"
    if final_state.get("route") == "tool_execution":
        return "tool_execution_completed"
    if final_state.get("route") == "knowledge_retrieval":
        return "knowledge_answer_generated"
    return "agent_v2_completed"


def _build_workflow_trace(final_state: dict[str, Any], timestamp: str) -> list[WorkflowTraceEvent]:
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

    if route == "clarification_needed":
        events.append(
            WorkflowTraceEvent(
                stage="clarification",
                status=workflow_status,
                timestamp=timestamp,
                detail=final_state.get("clarification_question") or "Clarification requested.",
            )
        )
    elif route == "tool_execution":
        events.append(
            WorkflowTraceEvent(
                stage="tool_execution",
                status=workflow_status,
                timestamp=timestamp,
                detail="Tool execution node completed in agent_v2.",
            )
        )
    else:
        events.append(
            WorkflowTraceEvent(
                stage="answer",
                status=workflow_status,
                timestamp=timestamp,
                detail=final_state.get("answer") or "Answer generated in agent_v2.",
            )
        )

    return events


def orchestrate_agent_v2_request(
    *,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
) -> AgentWorkflowResponse:
    normalized_question = question.strip()
    normalized_filename = filename.strip() if isinstance(filename, str) else None
    if not normalized_question:
        raise ValueError("question_must_not_be_empty")
    if top_k <= 0:
        raise ValueError("top_k_must_be_positive")

    graph = build_graph(checkpointer=checkpointer) if checkpointer is not None else agent_graph
    initial_state = _build_initial_state(
        question=normalized_question,
        filename=normalized_filename,
        top_k=top_k,
    )
    run_id = uuid.uuid4().hex
    invoke_config = _build_graph_invoke_config(run_id)
    final_state = graph.invoke(initial_state, config=invoke_config)
    timestamp = build_utc_timestamp()
    route_type = final_state.get("route") or "knowledge_retrieval"
    route_reason = final_state.get("route_reason") or "Route selected by agent_v2."
    answer = final_state.get("answer")
    answer_source = final_state.get("answer_source")
    retrieval = None

    if route_type == "knowledge_retrieval" and normalized_filename:
        try:
            query_response = run_query(
                filename=normalized_filename,
                question=normalized_question,
                top_k=top_k,
            )
            answer = query_response.answer
            answer_source = query_response.answer_source
            retrieval = query_response.retrieval
        except FileNotFoundError:
            pass

    tool_execution = None
    tool_chain = final_state.get("tool_chain") or []
    if tool_chain:
        last_step = tool_chain[-1]
        if isinstance(last_step, dict):
            tool_execution = last_step.get("tool_execution")

    clarification_question = final_state.get("clarification_question")

    return AgentWorkflowResponse(
        run_id=run_id,
        root_run_id=None,
        recovery_depth=0,
        question=normalized_question,
        workflow_status=final_state.get("workflow_status") or "completed",
        terminal_reason=_build_terminal_reason(final_state),
        started_at=timestamp,
        completed_at=timestamp,
        last_updated_at=timestamp,
        workflow_planning_mode=final_state.get("route_planning_mode"),
        route=RouteDecision(
            route_type=route_type,
            route_reason=route_reason,
            filename=normalized_filename,
        ),
        workflow_trace=_build_workflow_trace(final_state, timestamp),
        filename=normalized_filename,
        answer=answer,
        answer_source=answer_source,
        answered_at=timestamp if answer else None,
        retrieval=retrieval,
        clarification_message=clarification_question,
        tool_execution=tool_execution,
        tool_chain=tool_chain,
    )
