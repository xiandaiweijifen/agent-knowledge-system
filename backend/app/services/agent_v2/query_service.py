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
)
from app.services.agent_v2.graph import build_graph
from app.schemas.query import RetrievalResult
from app.services.agent_v2.response_builder import (
    _build_agent_v2_response,
    _build_recovery_metadata,
    _build_workflow_trace,
    _resolve_resumed_completed_at,
    _resolve_terminal_reason,
)
from app.services.agent_v2.run_store import (
    get_persisted_agent_v2_run,
    list_persisted_agent_v2_runs,
    persist_agent_v2_run,
)
from app.services.agent_v2.skill_catalog import _build_skill_metadata
from app.services.agent_v2.state_builder import _build_graph_invoke_config, _build_initial_state
from app.services.agent_v2.stream_events import (
    _build_stream_event,
    _merge_stream_update,
    _translate_stream_update_to_event,
)
from app.services.agent_v2.ticket_recovery import _resume_ticket_submission_confirmation
from app.services.agent_v2.tool_extraction import _extract_interrupt_payload
from app.services.agent_v2.tracing import finalize_agent_v2_trace, trace_agent_v2_run
from app.services.agent_v2.validation import _normalize_question, _normalize_top_k
from app.services.agent_v2.workflow_policy import (
    _build_workflow_policy,
    _is_ticket_submission_confirmation_plan,
)
from app.services.ingestion.document_service import build_utc_timestamp


def _execute_agent_v2_workflow(
    *,
    run_id: str,
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    checkpointer=None,
    debug_fault_injection: dict[str, Any] | None = None,
    resume_hints: dict[str, Any] | None = None,
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
        resume_hints=resume_hints,
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
        raise RuntimeError(
            "resume_requires_checkpointer: cannot resume a checkpoint-based workflow "
            "without an active PostgreSQL checkpointer. "
            "Ensure DATABASE_URL is configured and the backend started successfully."
        )

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
            workflow_family, enriched_tool_chain, available_skills, skill_trace = _build_skill_metadata(
                resumed_state,
                interrupt_payload,
                tool_chain,
            )
            terminal_reason = _resolve_terminal_reason(
                final_state=resumed_state,
                interrupt_payload=interrupt_payload,
            )
            workflow_outcome, recommended_next_actions = _build_workflow_policy(
                workflow_family=workflow_family,
                workflow_status=workflow_status,
                terminal_reason=terminal_reason,
                tool_chain=enriched_tool_chain,
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
                terminal_reason=terminal_reason,
                outcome_category=resumed_state.get("workflow_status") or persisted_run.outcome_category,
                workflow_outcome=workflow_outcome,
                recommended_next_actions=recommended_next_actions,
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
                step_count=len(enriched_tool_chain),
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
                workflow_family=workflow_family,
                available_skills=available_skills,
                skill_trace=skill_trace,
                retrieval=retrieval,
                clarification_message=clarification_question,
                clarification_plan=clarification_plan,
                tool_plan=tool_plan,
                tool_execution=tool_execution,
                tool_chain=enriched_tool_chain,
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
    resume_hints: dict[str, Any] = {}

    if selected_action == "resume_from_failed_step":
        # Collect successfully completed steps to reuse in the new run,
        # skipping the last failed step so only it gets retried.
        successful_steps = [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in source_run.tool_chain
            if (s.model_dump() if hasattr(s, "model_dump") else s).get("step_status") != "failed"
        ]
        if source_run.tool_chain:
            last_step = source_run.tool_chain[-1]
            failed_step_index = (
                last_step.step_index
                if hasattr(last_step, "step_index")
                else (last_step.get("step_index") if isinstance(last_step, dict) else None)
            )
        resume_hints = {
            "reuse_tool_chain": successful_steps,
            "skip_to_step": len(successful_steps),
        }

    return _execute_agent_v2_workflow(
        run_id=uuid.uuid4().hex,
        question=source_run.question,
        filename=source_run.filename,
        top_k=top_k,
        checkpointer=checkpointer,
        debug_fault_injection=debug_fault_injection,
        resume_hints=resume_hints if selected_action == "resume_from_failed_step" else None,
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
        reused_step_indices=list(range(len(resume_hints.get("reuse_tool_chain", [])))) if selected_action == "resume_from_failed_step" else [],
        retried_step_indices=[failed_step_index] if selected_action == "resume_from_failed_step" and failed_step_index is not None else [],
    )
