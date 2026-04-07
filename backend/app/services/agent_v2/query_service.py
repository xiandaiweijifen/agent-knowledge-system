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
from app.services.agent_v2.graph import build_graph
from app.schemas.query import RetrievalResult
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.agent_v2.run_store import (
    get_persisted_agent_v2_run,
    list_persisted_agent_v2_runs,
    persist_agent_v2_run,
)
from app.services.agent_v2.tracing import finalize_agent_v2_trace, trace_agent_v2_run


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
        "route": "",
        "route_reason": None,
        "route_planning_mode": None,
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
    tool_plan, tool_execution, tool_chain = _collect_tool_payload(final_state)
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
        retrieval=retrieval,
        clarification_message=clarification_question,
        clarification_plan=clarification_plan,
        tool_plan=tool_plan,
        tool_execution=tool_execution,
        tool_chain=tool_chain,
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


def orchestrate_agent_v2_request(
    *,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
) -> AgentWorkflowResponse:
    normalized_question = _normalize_question(question)
    normalized_filename = filename.strip() if isinstance(filename, str) else None
    top_k = _normalize_top_k(top_k)

    run_id = uuid.uuid4().hex
    graph = build_graph(checkpointer=checkpointer or InMemorySaver())
    initial_state = _build_initial_state(
        question=normalized_question,
        filename=normalized_filename,
        top_k=top_k,
    )
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
            persist_agent_v2_run(response)
            finalize_agent_v2_trace(trace_run, response=response)
            return response
        except Exception as exc:
            finalize_agent_v2_trace(trace_run, error=exc)
            raise


def stream_agent_v2_request(
    *,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
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
                outcome_category=persisted_run.outcome_category,
                is_recoverable=persisted_run.is_recoverable,
                retry_state=persisted_run.retry_state,
                recommended_recovery_action=persisted_run.recommended_recovery_action,
                available_recovery_actions=persisted_run.available_recovery_actions,
                recovery_action_details=persisted_run.recovery_action_details,
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
