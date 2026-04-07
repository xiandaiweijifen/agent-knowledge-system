import uuid
from typing import Any

from app.schemas.query import (
    AgentWorkflowResponse,
    AgentWorkflowRunListResponse,
    RouteDecision,
    WorkflowTraceEvent,
)
from app.services.agent_v2.graph import agent_graph, build_graph
from app.schemas.query import RetrievalResult
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.agent_v2.run_store import (
    get_persisted_agent_v2_run,
    list_persisted_agent_v2_runs,
    persist_agent_v2_run,
)


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
        "model": None,
        "answered_at": None,
        "answer_latency_ms": None,
        "chat_provider": None,
        "chat_model": None,
        "workflow_status": "in_progress",
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
    workflow_status = final_state.get("workflow_status")
    if workflow_status == "clarification_required":
        return "clarification_requested"
    if final_state.get("route") == "tool_execution":
        return "tool_execution_completed"
    if final_state.get("route") == "knowledge_retrieval":
        return "knowledge_answer_generated"
    return "agent_v2_completed"


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

    if route == "clarification_needed":
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
                detail=answer_detail or final_state.get("answer") or "Answer generated in agent_v2.",
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
    model = final_state.get("model")
    answered_at = final_state.get("answered_at") or (timestamp if answer else None)
    answer_latency_ms = final_state.get("answer_latency_ms")
    chat_provider = final_state.get("chat_provider")
    chat_model = final_state.get("chat_model")
    retrieval_payload = final_state.get("retrieval_result")
    retrieval = RetrievalResult.model_validate(retrieval_payload) if retrieval_payload else None

    tool_execution = None
    tool_plan = None
    tool_chain = final_state.get("tool_chain") or []
    if tool_chain:
        last_step = tool_chain[-1]
        if isinstance(last_step, dict):
            tool_plan = last_step.get("tool_plan")
            tool_execution = last_step.get("tool_execution")

    clarification_question = final_state.get("clarification_question")

    response = AgentWorkflowResponse(
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
        workflow_trace=_build_workflow_trace(
            final_state,
            timestamp=timestamp,
            answer_detail=answer,
            clarification_detail=clarification_question,
        ),
        filename=normalized_filename,
        answer=answer,
        answer_source=answer_source,
        model=model,
        answered_at=answered_at,
        answer_latency_ms=answer_latency_ms,
        chat_provider=chat_provider,
        chat_model=chat_model,
        retrieval=retrieval,
        clarification_message=clarification_question,
        tool_plan=tool_plan,
        tool_execution=tool_execution,
        tool_chain=tool_chain,
    )
    persist_agent_v2_run(response)
    return response


def resume_agent_v2_request(
    *,
    run_id: str,
    checkpointer=None,
) -> AgentWorkflowResponse:
    persisted_run = get_persisted_agent_v2_run(run_id)
    if checkpointer is None:
        return persisted_run

    graph = build_graph(checkpointer=checkpointer)
    invoke_config = _build_graph_invoke_config(run_id)
    snapshot = graph.get_state(invoke_config)
    if not snapshot.values:
        return persisted_run

    resumed_state = graph.invoke(None, config=invoke_config)
    timestamp = build_utc_timestamp()
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
        applied_clarification_fields=persisted_run.applied_clarification_fields,
        question_rewritten=persisted_run.question_rewritten,
        overridden_plan_arguments=persisted_run.overridden_plan_arguments,
        workflow_status=resumed_state.get("workflow_status") or persisted_run.workflow_status,
        terminal_reason=_build_terminal_reason(resumed_state),
        outcome_category=persisted_run.outcome_category,
        is_recoverable=persisted_run.is_recoverable,
        retry_state=persisted_run.retry_state,
        recommended_recovery_action=persisted_run.recommended_recovery_action,
        available_recovery_actions=persisted_run.available_recovery_actions,
        recovery_action_details=persisted_run.recovery_action_details,
        failure_stage=resumed_state.get("failure_stage") or persisted_run.failure_stage,
        failure_message=resumed_state.get("error") or persisted_run.failure_message,
        started_at=persisted_run.started_at,
        completed_at=timestamp if (resumed_state.get("workflow_status") or persisted_run.workflow_status) == "completed" else persisted_run.completed_at,
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
        retry_count=persisted_run.retry_count,
        retried_step_indices=persisted_run.retried_step_indices,
        step_count=persisted_run.step_count,
        route=RouteDecision(
            route_type=route_type,
            route_reason=route_reason,
            filename=resumed_state.get("filename") or persisted_run.filename,
        ),
        workflow_trace=_build_workflow_trace(
            resumed_state,
            timestamp=timestamp,
            answer_detail=answer,
            clarification_detail=resumed_state.get("clarification_question") or persisted_run.clarification_message,
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
        clarification_message=resumed_state.get("clarification_question") or persisted_run.clarification_message,
        clarification_plan=persisted_run.clarification_plan,
        tool_plan=tool_plan,
        tool_execution=tool_execution,
        tool_chain=tool_chain,
    )
    persist_agent_v2_run(response)
    return response


def list_agent_v2_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    return list_persisted_agent_v2_runs(limit=limit)
