import json
import re
import uuid
from pathlib import Path

from app.schemas.query import (
    AgentWorkflowMigrationResponse,
    AgentWorkflowRunPruneResponse,
    AgentWorkflowResponse,
    AgentWorkflowRunListResponse,
    AgentWorkflowRunSummary,
    AgentWorkflowRunResetResponse,
    AgentWorkflowRunStatsResponse,
    WorkflowTraceEvent,
)
from app.schemas.tools import ToolExecutionRequest
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.agent.state_store import JsonListRepository
from app.services.agent.clarification_service import (
    plan_clarification,
    plan_unsupported_action_clarification,
    plan_search_miss_clarification,
    plan_search_summary_miss_clarification,
)
from app.services.llm.workflow_planner_service import generate_llm_workflow_plan
from app.services.agent.query_service import run_query
from app.services.agent.router_service import route_request
from app.services.agent.tool_service import (
    _extract_search_max_results_argument,
    execute_tool_request,
    plan_tool_request,
)

WORKFLOW_RUN_DATA_DIR = Path("../data/tool_state")
WORKFLOW_RUN_DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOW_RUN_STORE_PATH = WORKFLOW_RUN_DATA_DIR / "workflow_runs.json"

SEARCH_AND_TICKET_PATTERN = re.compile(
    r"(?P<search>^(?:search|find|lookup|look up).+?)(?:\s+and\s+|\s*,?\s+then\s+)(?P<ticket>(?:create|open).+\bticket\b.+)$",
    re.IGNORECASE,
)
SEARCH_AND_SUMMARIZE_PATTERN = re.compile(
    r"(?P<search>^(?:search|find|lookup|look up).+?)(?:\s+and\s+|\s*,?\s+then\s+)(?P<summarize>summari[sz]e.+)$",
    re.IGNORECASE,
)
UNSUPPORTED_DIRECT_ACTION_PATTERN = re.compile(
    r"\b(restart|deploy|rollback|delete|remove|shutdown|stop|start)\b",
    re.IGNORECASE,
)
EXPLICIT_TICKET_INTENT_PATTERN = re.compile(r"\b(ticket|incident)\b", re.IGNORECASE)
SEARCH_STYLE_PREFIX_PATTERN = re.compile(
    r"^\s*(search|find|lookup|look up|show|inspect|check|query|list)\b",
    re.IGNORECASE,
)
ENVIRONMENT_HINT_PATTERN = re.compile(r"\b(production|staging|development|dev)\b", re.IGNORECASE)
SEVERITY_HINT_PATTERN = re.compile(r"\b(high|medium|low)\b", re.IGNORECASE)


def _load_workflow_runs() -> list[dict]:
    return JsonListRepository(WORKFLOW_RUN_STORE_PATH).load()


def _save_workflow_runs(runs: list[dict]) -> None:
    JsonListRepository(WORKFLOW_RUN_STORE_PATH).save(runs)


def _normalize_persisted_workflow_step_records(
    run: dict,
) -> list[dict]:
    normalized_steps: list[dict] = []
    tool_chain = run.get("tool_chain")
    if not isinstance(tool_chain, list):
        return normalized_steps

    fallback_started_at = run.get("started_at") or run.get("completed_at")
    fallback_completed_at = run.get("completed_at") or run.get("last_updated_at") or fallback_started_at

    for index, raw_step in enumerate(tool_chain, start=1):
        if not isinstance(raw_step, dict):
            continue

        if {"step_id", "step_index", "step_status", "started_at"}.issubset(raw_step):
            normalized_step = dict(raw_step)
            normalized_step.setdefault("failure_message", None)
            normalized_steps.append(normalized_step)
            continue

        tool_execution = raw_step.get("tool_execution")
        execution_status = "completed"
        executed_at = None
        if isinstance(tool_execution, dict):
            execution_status = tool_execution.get("execution_status", "completed")
            executed_at = tool_execution.get("executed_at")

        started_at = raw_step.get("started_at") or executed_at or fallback_started_at
        completed_at = raw_step.get("completed_at") or executed_at or fallback_completed_at

        normalized_steps.append(
            {
                "step_id": f"step_{index}",
                "step_index": index,
                "step_status": execution_status,
                "started_at": started_at,
                "completed_at": completed_at,
                "question": raw_step.get("question", run.get("question", "")),
                "tool_plan": raw_step.get("tool_plan", {}),
                "tool_execution": tool_execution if isinstance(tool_execution, dict) else None,
                "failure_message": raw_step.get("failure_message"),
            }
        )

    return normalized_steps


def _normalize_persisted_workflow_run(run: dict) -> dict:
    normalized_run = dict(run)
    normalized_run["tool_chain"] = _normalize_persisted_workflow_step_records(normalized_run)
    normalized_run["step_count"] = _backfill_step_count(normalized_run)
    normalized_run["started_at"] = _backfill_started_at(normalized_run)
    normalized_run["completed_at"] = _backfill_completed_at(normalized_run)
    normalized_run["last_updated_at"] = _backfill_last_updated_at(normalized_run)
    normalized_run["terminal_reason"] = _backfill_terminal_reason(normalized_run)
    normalized_run["workflow_planning_mode"] = (
        normalized_run.get("workflow_planning_mode")
        or _extract_workflow_planning_mode_from_trace(normalized_run.get("workflow_trace", []))
    )
    normalized_run["tool_planning_mode"] = (
        normalized_run.get("tool_planning_mode")
        or _extract_tool_planning_mode(normalized_run)
    )
    normalized_run["clarification_planning_mode"] = (
        normalized_run.get("clarification_planning_mode")
        or _extract_clarification_planning_mode(normalized_run)
    )
    return normalized_run


def _workflow_trace_timestamps(run: dict) -> list[str]:
    trace = run.get("workflow_trace")
    if not isinstance(trace, list):
        return []
    timestamps: list[str] = []
    for event in trace:
        if isinstance(event, dict):
            timestamp = event.get("timestamp")
            if isinstance(timestamp, str) and timestamp.strip():
                timestamps.append(timestamp)
    return timestamps


def _tool_chain_step_records(run: dict) -> list[dict]:
    tool_chain = run.get("tool_chain")
    if not isinstance(tool_chain, list):
        return []
    return [step for step in tool_chain if isinstance(step, dict)]


def _backfill_step_count(run: dict) -> int:
    existing = run.get("step_count")
    if isinstance(existing, int) and existing > 0:
        return existing
    return len(_tool_chain_step_records(run))


def _backfill_started_at(run: dict) -> str | None:
    existing = run.get("started_at")
    if isinstance(existing, str) and existing.strip():
        return existing

    trace_timestamps = _workflow_trace_timestamps(run)
    if trace_timestamps:
        return trace_timestamps[0]

    for step in _tool_chain_step_records(run):
        started_at = step.get("started_at")
        if isinstance(started_at, str) and started_at.strip():
            return started_at

    for step in _tool_chain_step_records(run):
        completed_at = step.get("completed_at")
        if isinstance(completed_at, str) and completed_at.strip():
            return completed_at

    return None


def _backfill_completed_at(run: dict) -> str | None:
    existing = run.get("completed_at")
    if isinstance(existing, str) and existing.strip():
        return existing

    if run.get("workflow_status") != "completed":
        return None

    trace_timestamps = _workflow_trace_timestamps(run)
    if trace_timestamps:
        return trace_timestamps[-1]

    step_records = _tool_chain_step_records(run)
    if step_records:
        completed_at = step_records[-1].get("completed_at")
        if isinstance(completed_at, str) and completed_at.strip():
            return completed_at

    tool_execution = run.get("tool_execution")
    if isinstance(tool_execution, dict):
        executed_at = tool_execution.get("executed_at")
        if isinstance(executed_at, str) and executed_at.strip():
            return executed_at

    answered_at = run.get("answered_at")
    if isinstance(answered_at, str) and answered_at.strip():
        return answered_at

    return None


def _backfill_last_updated_at(run: dict) -> str | None:
    existing = run.get("last_updated_at")
    if isinstance(existing, str) and existing.strip():
        return existing

    trace_timestamps = _workflow_trace_timestamps(run)
    if trace_timestamps:
        return trace_timestamps[-1]

    completed_at = run.get("completed_at")
    if isinstance(completed_at, str) and completed_at.strip():
        return completed_at

    started_at = run.get("started_at")
    if isinstance(started_at, str) and started_at.strip():
        return started_at

    return None


def _backfill_terminal_reason(run: dict) -> str | None:
    existing = run.get("terminal_reason")
    if isinstance(existing, str) and existing.strip():
        return existing

    workflow_status = run.get("workflow_status")
    clarification_plan = run.get("clarification_plan")
    answer_source = run.get("answer_source")
    tool_execution = run.get("tool_execution")
    step_records = _tool_chain_step_records(run)
    final_step_execution = None
    if step_records:
        candidate_execution = step_records[-1].get("tool_execution")
        if isinstance(candidate_execution, dict):
            final_step_execution = candidate_execution

    if workflow_status == "completed":
        if answer_source == "local_search_summary":
            return "search_summary_completed"
        if answer_source:
            return "knowledge_answer_generated"
        if isinstance(tool_execution, dict):
            return "tool_execution_completed"
        if isinstance(final_step_execution, dict):
            return "tool_execution_completed"

    if workflow_status == "clarification_required":
        if isinstance(clarification_plan, dict):
            missing_fields = clarification_plan.get("missing_fields")
            if isinstance(missing_fields, list):
                missing_field_set = {field for field in missing_fields if isinstance(field, str)}
                if {"search_query_refinement", "document_scope"}.issubset(missing_field_set):
                    question = run.get("question", "")
                    if isinstance(question, str) and re.search(r"\bsummari[sz]e\b", question, re.IGNORECASE):
                        return "search_summary_miss_clarification"
                    return "search_miss_clarification"
        return "clarification_requested"

    return None


def _workflow_run_requires_migration(run: dict) -> bool:
    normalized_run = _normalize_persisted_workflow_run(run)
    migration_fields = (
        "tool_chain",
        "step_count",
        "started_at",
        "completed_at",
        "last_updated_at",
        "terminal_reason",
        "workflow_planning_mode",
        "tool_planning_mode",
        "clarification_planning_mode",
    )
    return any(run.get(field) != normalized_run.get(field) for field in migration_fields)


def _extract_workflow_planning_mode_from_trace(trace: list[dict] | list[WorkflowTraceEvent]) -> str | None:
    for event in trace:
        if isinstance(event, WorkflowTraceEvent):
            stage = event.stage
            detail = event.detail
        elif isinstance(event, dict):
            stage = event.get("stage")
            detail = event.get("detail")
        else:
            continue
        if stage != "workflow_planning" or not isinstance(detail, str):
            continue
        match = re.search(r"\bvia\s+(.+?)\.$", detail.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_tool_planning_mode(response: AgentWorkflowResponse | dict) -> str | None:
    if isinstance(response, AgentWorkflowResponse):
        tool_plan = response.tool_plan
        tool_chain = response.tool_chain
    else:
        tool_plan = response.get("tool_plan")
        tool_chain = response.get("tool_chain")

    if isinstance(tool_plan, dict):
        planning_mode = tool_plan.get("planning_mode")
        if isinstance(planning_mode, str) and planning_mode.strip():
            return planning_mode

    if isinstance(tool_chain, list):
        for step in reversed(tool_chain):
            if isinstance(step, dict):
                step_tool_plan = step.get("tool_plan")
            else:
                step_tool_plan = step.tool_plan
            if isinstance(step_tool_plan, dict):
                planning_mode = step_tool_plan.get("planning_mode")
                if isinstance(planning_mode, str) and planning_mode.strip():
                    return planning_mode
    return None


def _extract_clarification_planning_mode(response: AgentWorkflowResponse | dict) -> str | None:
    clarification_plan = (
        response.clarification_plan
        if isinstance(response, AgentWorkflowResponse)
        else response.get("clarification_plan")
    )
    if isinstance(clarification_plan, dict):
        planning_mode = clarification_plan.get("planning_mode")
        if isinstance(planning_mode, str) and planning_mode.strip():
            return planning_mode
    return None


def _annotate_planner_modes(response: AgentWorkflowResponse) -> AgentWorkflowResponse:
    response.workflow_planning_mode = _extract_workflow_planning_mode_from_trace(response.workflow_trace)
    response.tool_planning_mode = _extract_tool_planning_mode(response)
    response.clarification_planning_mode = _extract_clarification_planning_mode(response)
    return response


def _extract_final_tool_identity(run: AgentWorkflowResponse) -> tuple[str | None, str | None]:
    if run.tool_execution:
        return run.tool_execution.get("tool_name"), run.tool_execution.get("action")

    if run.tool_chain:
        final_step = run.tool_chain[-1]
        if final_step.tool_execution:
            return (
                final_step.tool_execution.get("tool_name"),
                final_step.tool_execution.get("action"),
            )
        if final_step.tool_plan:
            return final_step.tool_plan.get("tool_name"), final_step.tool_plan.get("action")

    if run.tool_plan:
        return run.tool_plan.get("tool_name"), run.tool_plan.get("action")

    return None, None


def _persist_workflow_response(
    response: AgentWorkflowResponse,
    resumed_from_question: str | None = None,
    source_run_id: str | None = None,
) -> AgentWorkflowResponse:
    response = _annotate_planner_modes(response)
    response.run_id = uuid.uuid4().hex
    response.resumed_from_question = resumed_from_question
    response.source_run_id = source_run_id
    runs = _load_workflow_runs()
    runs.append(response.model_dump())
    _save_workflow_runs(runs)
    return response


def _finalize_workflow_response(
    response: AgentWorkflowResponse,
    *,
    started_at: str,
    terminal_reason: str,
    completed_at: str | None = None,
    last_updated_at: str | None = None,
) -> AgentWorkflowResponse:
    response.terminal_reason = terminal_reason
    response.started_at = started_at
    response.completed_at = completed_at
    response.last_updated_at = last_updated_at or completed_at or started_at
    return _annotate_planner_modes(response)


def _format_failure_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{exc.__class__.__name__}: {message}"
    return exc.__class__.__name__


def _build_failed_workflow_response(
    *,
    question: str,
    route,
    workflow_trace: list[WorkflowTraceEvent],
    filename: str | None,
    started_at: str,
    failed_at: str,
    terminal_reason: str,
    failure_stage: str,
    failure_message: str,
    step_count: int = 0,
    tool_plan: dict | None = None,
    tool_execution: dict | None = None,
    tool_chain: list[dict] | None = None,
) -> AgentWorkflowResponse:
    response = AgentWorkflowResponse(
        question=question,
        workflow_status="failed",
        route=route,
        workflow_trace=workflow_trace,
        filename=filename,
        terminal_reason=terminal_reason,
        failure_stage=failure_stage,
        failure_message=failure_message,
        step_count=step_count,
        tool_plan=tool_plan,
        tool_execution=tool_execution,
        tool_chain=tool_chain or [],
    )
    return _finalize_workflow_response(
        response,
        started_at=started_at,
        terminal_reason=terminal_reason,
        completed_at=failed_at,
    )


def get_persisted_workflow_run(run_id: str) -> AgentWorkflowResponse:
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        raise ValueError("run_id_must_not_be_empty")

    for run in reversed(_load_workflow_runs()):
        if run.get("run_id") == normalized_run_id:
            return AgentWorkflowResponse.model_validate(_normalize_persisted_workflow_run(run))

    raise FileNotFoundError(run_id)


def list_persisted_workflow_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    if limit <= 0:
        raise ValueError("limit_must_be_positive")

    persisted_runs = [
        AgentWorkflowResponse.model_validate(_normalize_persisted_workflow_run(run))
        for run in reversed(_load_workflow_runs())
    ][:limit]

    return AgentWorkflowRunListResponse(
        runs=[
            AgentWorkflowRunSummary(
                run_id=run.run_id or "",
                question=run.question,
                resumed_from_question=run.resumed_from_question,
                source_run_id=run.source_run_id,
                resume_source_type=run.resume_source_type,
                resume_strategy=run.resume_strategy,
                applied_clarification_fields=run.applied_clarification_fields,
                question_rewritten=run.question_rewritten,
                overridden_plan_arguments=run.overridden_plan_arguments,
                workflow_status=run.workflow_status,
                terminal_reason=run.terminal_reason,
                failure_stage=run.failure_stage,
                failure_message=run.failure_message,
                started_at=run.started_at,
                completed_at=run.completed_at,
                last_updated_at=run.last_updated_at,
                workflow_planning_mode=run.workflow_planning_mode,
                tool_planning_mode=run.tool_planning_mode,
                clarification_planning_mode=run.clarification_planning_mode,
                step_count=run.step_count,
                route_type=run.route.route_type,
                route_reason=run.route.route_reason,
                filename=run.filename,
                answered_at=run.answered_at,
                answer_source=run.answer_source,
                final_tool_name=_extract_final_tool_identity(run)[0],
                final_tool_action=_extract_final_tool_identity(run)[1],
            )
            for run in persisted_runs
            if run.run_id
        ]
    )


def migrate_persisted_workflow_runs() -> AgentWorkflowMigrationResponse:
    runs = _load_workflow_runs()
    migrated_runs: list[dict] = []
    migrated_run_count = 0
    migrated_step_count = 0

    for run in runs:
        normalized_run = _normalize_persisted_workflow_run(run)
        migrated_runs.append(normalized_run)

        if _workflow_run_requires_migration(run):
            migrated_run_count += 1
            original_steps = run.get("tool_chain")
            if isinstance(original_steps, list):
                migrated_step_count += len(normalized_run.get("tool_chain", []))

    if migrated_run_count:
        _save_workflow_runs(migrated_runs)

    return AgentWorkflowMigrationResponse(
        migrated_run_count=migrated_run_count,
        migrated_step_count=migrated_step_count,
        total_run_count=len(runs),
    )


def get_workflow_run_stats() -> AgentWorkflowRunStatsResponse:
    persisted_runs = [
        AgentWorkflowResponse.model_validate(_normalize_persisted_workflow_run(run))
        for run in _load_workflow_runs()
    ]
    latest_run = persisted_runs[-1] if persisted_runs else None

    return AgentWorkflowRunStatsResponse(
        total_run_count=len(persisted_runs),
        completed_run_count=sum(1 for run in persisted_runs if run.workflow_status == "completed"),
        clarification_required_run_count=sum(
            1 for run in persisted_runs if run.workflow_status == "clarification_required"
        ),
        failed_run_count=sum(1 for run in persisted_runs if run.workflow_status == "failed"),
        latest_run_id=latest_run.run_id if latest_run else None,
        latest_updated_at=latest_run.last_updated_at if latest_run else None,
    )


def prune_persisted_workflow_runs(retain: int) -> AgentWorkflowRunPruneResponse:
    if retain < 0:
        raise ValueError("retain_must_not_be_negative")

    runs = _load_workflow_runs()
    total_run_count_before = len(runs)
    retained_runs = runs[-retain:] if retain > 0 else []
    removed_run_count = total_run_count_before - len(retained_runs)

    if removed_run_count > 0:
        _save_workflow_runs(retained_runs)

    return AgentWorkflowRunPruneResponse(
        total_run_count_before=total_run_count_before,
        retained_run_count=len(retained_runs),
        removed_run_count=removed_run_count,
    )


def reset_persisted_workflow_runs(confirm: bool) -> AgentWorkflowRunResetResponse:
    if not confirm:
        raise ValueError("reset_confirmation_required")

    runs = _load_workflow_runs()
    removed_run_count = len(runs)
    _save_workflow_runs([])
    return AgentWorkflowRunResetResponse(removed_run_count=removed_run_count)


def _match_search_then_ticket_workflow(question: str) -> tuple[str, str] | None:
    match = SEARCH_AND_TICKET_PATTERN.match(question.strip())
    if not match:
        return None

    return match.group("search").strip(), match.group("ticket").strip()


def _match_search_then_summarize_workflow(question: str) -> tuple[str, str] | None:
    match = SEARCH_AND_SUMMARIZE_PATTERN.match(question.strip())
    if not match:
        return None

    return match.group("search").strip(), match.group("summarize").strip()


def _resolve_multistep_workflow(question: str) -> tuple[str | None, str | None, str | None, str | None]:
    planning_mode, llm_plan = generate_llm_workflow_plan(question)

    if llm_plan is not None:
        workflow_kind = llm_plan["workflow_kind"]
        if workflow_kind in {"search_then_ticket", "search_then_summarize"}:
            return (
                workflow_kind,
                llm_plan["search_question"],
                llm_plan["follow_up_question"],
                planning_mode,
            )
        planning_mode = "heuristic_fallback_invalid_llm_workflow_plan"
    elif planning_mode.startswith("llm_"):
        planning_mode = "heuristic_fallback_invalid_llm_workflow_plan"

    search_then_ticket = _match_search_then_ticket_workflow(question)
    if search_then_ticket is not None:
        return "search_then_ticket", search_then_ticket[0], search_then_ticket[1], planning_mode

    search_then_summarize = _match_search_then_summarize_workflow(question)
    if search_then_summarize is not None:
        return "search_then_summarize", search_then_summarize[0], search_then_summarize[1], planning_mode

    return None, None, None, planning_mode


def _describe_workflow_planning_mode(planning_mode: str) -> str:
    normalized_mode = planning_mode.strip()
    if normalized_mode.startswith("llm_"):
        return normalized_mode
    if normalized_mode == "heuristic_stub":
        return "heuristic workflow matcher"
    if normalized_mode.startswith("heuristic_fallback_"):
        reason = normalized_mode.removeprefix("heuristic_fallback_").replace("_", " ")
        if reason.startswith("after "):
            return f"heuristic workflow matcher {reason}"
        return f"heuristic workflow matcher after {reason}"
    return "heuristic workflow matcher"


def _build_search_context_arguments(tool_output: dict[str, str]) -> dict[str, str]:
    arguments: dict[str, str] = {}

    query = tool_output.get("query", "").strip()
    matched_documents = tool_output.get("matched_documents", "").strip()
    snippets = tool_output.get("snippets", "").strip()
    matched_count = tool_output.get("matched_count", "").strip()

    if query:
        arguments["supporting_query"] = query
    if matched_documents:
        arguments["supporting_documents"] = matched_documents
    if snippets:
        arguments["supporting_snippets"] = snippets
    if matched_count:
        arguments["supporting_match_count"] = matched_count

    return arguments


def _split_search_snippets(snippets: str) -> list[tuple[str | None, str]]:
    parsed_snippets: list[tuple[str | None, str]] = []
    for raw_snippet in snippets.split(" | "):
        snippet = raw_snippet.strip()
        if not snippet:
            continue
        if ": " in snippet:
            source, content = snippet.split(": ", maxsplit=1)
            parsed_snippets.append((source.strip(), content.strip()))
        else:
            parsed_snippets.append((None, snippet))
    return parsed_snippets


def _ensure_summary_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _build_search_summary(tool_output: dict[str, str]) -> str:
    query = tool_output.get("query", "").strip()
    matched_count = tool_output.get("matched_count", "0").strip()
    returned_count = tool_output.get("returned_count", matched_count).strip()
    matched_documents = tool_output.get("matched_documents", "").strip()
    snippets = tool_output.get("snippets", "").strip()
    top_match_document = tool_output.get("top_match_document", "").strip()
    filename_filter = tool_output.get("filename_filter", "").strip()
    max_results = tool_output.get("max_results", "").strip()
    parsed_snippets = _split_search_snippets(snippets)

    summary_parts: list[str] = []

    if query:
        if filename_filter:
            summary_parts.append(
                f"I searched '{filename_filter}' for '{query}' and found {matched_count} matching result(s)."
            )
        else:
            summary_parts.append(
                f"I found {matched_count} matching document(s) for '{query}' and returned {returned_count} result(s)."
            )

    if max_results and matched_count and returned_count and matched_count != returned_count:
        summary_parts.append(
            f"Showing the top {returned_count} result(s) out of {matched_count} total matches."
        )

    if top_match_document:
        summary_parts.append(f"The strongest supporting document is {top_match_document}.")

    if matched_documents:
        document_list = [item.strip() for item in matched_documents.split(",") if item.strip()]
        if len(document_list) > 1:
            summary_parts.append(f"Returned documents: {', '.join(document_list)}.")

    if parsed_snippets:
        first_source, first_snippet = parsed_snippets[0]
        first_snippet = _ensure_summary_sentence(first_snippet)
        if first_source:
            summary_parts.append(f"Key evidence from {first_source}: {first_snippet}")
        else:
            summary_parts.append(f"Key evidence: {first_snippet}")

    if len(parsed_snippets) > 1:
        second_source, second_snippet = parsed_snippets[1]
        second_snippet = _ensure_summary_sentence(second_snippet)
        if second_source and second_source != top_match_document:
            summary_parts.append(f"Additional support from {second_source}: {second_snippet}")

    return " ".join(summary_parts).strip()


def _extract_summary_step_context(summarize_question: str) -> dict[str, str]:
    context: dict[str, str] = {}
    max_results = _extract_search_max_results_argument(summarize_question)
    if max_results:
        context["max_results"] = max_results
    return context


def _build_workflow_step_record(
    *,
    step_index: int,
    step_question: str,
    tool_plan: dict,
    tool_execution: dict,
    started_at: str,
    completed_at: str,
) -> dict:
    return {
        "step_id": f"step_{step_index}",
        "step_index": step_index,
        "step_status": tool_execution.get("execution_status", "completed"),
        "started_at": started_at,
        "completed_at": completed_at,
        "question": step_question,
        "tool_plan": tool_plan,
        "tool_execution": tool_execution,
    }


def _build_failed_workflow_step_record(
    *,
    step_index: int,
    step_question: str,
    started_at: str,
    completed_at: str,
    failure_message: str,
    tool_plan: dict | None = None,
    tool_execution: dict | None = None,
) -> dict:
    return {
        "step_id": f"step_{step_index}",
        "step_index": step_index,
        "step_status": "failed",
        "started_at": started_at,
        "completed_at": completed_at,
        "question": step_question,
        "tool_plan": tool_plan or {},
        "tool_execution": tool_execution,
        "failure_message": failure_message,
    }


def _normalize_confirmation(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "confirmed", "continue"}


def _extract_resume_ticket_overrides(clarification_context: dict[str, str]) -> dict[str, str]:
    overrides: dict[str, str] = {}

    for key in ("environment", "severity", "status", "ticket_id"):
        value = clarification_context.get(key, "").strip()
        if value:
            overrides[key] = value

    return overrides


def _extract_applied_clarification_fields(
    clarification_context: dict[str, str],
) -> list[str]:
    return sorted(
        key for key, value in clarification_context.items() if isinstance(value, str) and value.strip()
    )


def _extract_overridden_plan_arguments(
    clarification_context: dict[str, str],
) -> list[str]:
    overridden_arguments: set[str] = set()

    if clarification_context.get("search_query_refinement", "").strip():
        overridden_arguments.add("target")
    if clarification_context.get("document_scope", "").strip() or clarification_context.get(
        "filename", ""
    ).strip():
        overridden_arguments.add("filename")

    for key in ("environment", "severity", "status", "ticket_id"):
        if clarification_context.get(key, "").strip():
            overridden_arguments.add(key)

    return sorted(overridden_arguments)


def _resume_search_question(
    search_question: str,
    clarification_context: dict[str, str],
) -> str:
    query_override = clarification_context.get("search_query_refinement", "").strip()
    filename_override = (
        clarification_context.get("document_scope", "").strip()
        or clarification_context.get("filename", "").strip()
    )

    search_plan = plan_tool_request(search_question)
    resolved_query = query_override or search_plan.target

    if filename_override:
        return f"Search {filename_override} for {resolved_query}"

    if search_plan.arguments.get("filename"):
        return f"Search {search_plan.arguments['filename']} for {resolved_query}"

    return f"Search docs for {resolved_query}"


def _resume_ticket_question(
    ticket_question: str,
    clarification_context: dict[str, str],
) -> str:
    updated_question = ticket_question.strip()
    environment = clarification_context.get("environment", "").strip().lower()

    if environment and environment in {"production", "staging"}:
        if environment not in updated_question.lower():
            updated_question = f"{updated_question} in {environment}"

    return updated_question


def _resume_generic_question(
    original_question: str,
    clarification_context: dict[str, str],
) -> str:
    tokens: list[str] = []
    for key, value in clarification_context.items():
        if not value.strip():
            continue
        label = key.replace("_", " ")
        tokens.append(f"{label}: {value.strip()}")

    if not tokens:
        return original_question

    return f"{original_question} {' '.join(tokens)}"


def _resolve_resume_source(
    original_question: str | None,
    run_id: str | None,
) -> tuple[str, str | None, str | None, str]:
    normalized_question = (original_question or "").strip()
    normalized_run_id = (run_id or "").strip()

    if normalized_question:
        return normalized_question, None, None, "original_question"

    if not normalized_run_id:
        raise ValueError("original_question_or_run_id_required")

    persisted_run = get_persisted_workflow_run(normalized_run_id)
    return persisted_run.question, persisted_run.filename, persisted_run.run_id, "run_id"


def _requires_unsupported_action_clarification(question: str) -> bool:
    normalized_question = question.strip()
    if not UNSUPPORTED_DIRECT_ACTION_PATTERN.search(normalized_question):
        return False
    if SEARCH_STYLE_PREFIX_PATTERN.search(normalized_question):
        return False
    if EXPLICIT_TICKET_INTENT_PATTERN.search(normalized_question):
        return False
    return True


def _build_unsupported_action_fallback_plan(question: str, target: str) -> dict:
    normalized_question = question.strip()
    normalized_target = target.strip() or "target-system"
    arguments = {
        "description": normalized_question,
        "service_name": normalized_target,
    }

    environment_match = ENVIRONMENT_HINT_PATTERN.search(normalized_question)
    if environment_match:
        arguments["environment"] = environment_match.group(1).lower()

    severity_match = SEVERITY_HINT_PATTERN.search(normalized_question)
    if severity_match:
        arguments["severity"] = severity_match.group(1).lower()

    return {
        "question": normalized_question,
        "planning_mode": "guardrail_ticket_fallback",
        "route_hint": "tool_execution",
        "tool_name": "ticketing",
        "action": "create",
        "target": normalized_target,
        "arguments": arguments,
        "plan_summary": (
            f"Fallback to ticketing:create for {normalized_target} because direct operational "
            "execution is not supported yet."
        ),
    }


def resume_agent_request(
    original_question: str | None,
    clarification_context: dict[str, str],
    run_id: str | None = None,
    filename: str | None = None,
    top_k: int = 3,
) -> AgentWorkflowResponse:
    if not clarification_context:
        raise ValueError("clarification_context_required")

    source_question, source_filename, source_run_id, resume_source_type = _resolve_resume_source(
        original_question, run_id
    )
    resumed_question = source_question.strip()
    applied_clarification_fields = _extract_applied_clarification_fields(clarification_context)
    overridden_plan_arguments = _extract_overridden_plan_arguments(clarification_context)
    resume_strategy = "generic_clarification_resume"

    workflow_kind, workflow_search_question, workflow_follow_up_question, _ = _resolve_multistep_workflow(
        resumed_question
    )

    if workflow_kind == "search_then_ticket" and workflow_search_question and workflow_follow_up_question:
        resume_strategy = "search_then_ticket_resume"
        search_question, ticket_question = workflow_search_question, workflow_follow_up_question
        resumed_search = _resume_search_question(search_question, clarification_context)
        resumed_ticket = _resume_ticket_question(ticket_question, clarification_context)
        execution_confirmed = _normalize_confirmation(
            clarification_context.get("execution_confirmation", "")
        )

        if not clarification_context.get("search_query_refinement", "").strip() and not execution_confirmed:
            raise ValueError("search_query_refinement_or_execution_confirmation_required")

        resumed_question = f"{resumed_search} and {resumed_ticket}"

    elif (
        workflow_kind == "search_then_summarize"
        and workflow_search_question
        and workflow_follow_up_question
    ):
        resume_strategy = "search_then_summarize_resume"
        search_question, summarize_question = workflow_search_question, workflow_follow_up_question
        resumed_search = _resume_search_question(search_question, clarification_context)
        resumed_question = f"{resumed_search} and {summarize_question}"

    else:
        resumed_question = _resume_generic_question(original_question, clarification_context)

    response = orchestrate_agent_request(
        question=resumed_question,
        filename=filename if filename is not None else source_filename,
        top_k=top_k,
        resume_context=clarification_context,
        persist_run=False,
    )
    response.workflow_trace.insert(
        0,
        WorkflowTraceEvent(
            stage="workflow_resume",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=(
                f"Resumed workflow from '{source_question}' via {resume_source_type} using "
                f"{resume_strategy} with fields: "
                f"{', '.join(applied_clarification_fields) if applied_clarification_fields else 'none'}; "
                f"overridden arguments: "
                f"{', '.join(overridden_plan_arguments) if overridden_plan_arguments else 'none'}."
            ),
        ),
    )
    response.question = resumed_question
    response.resume_source_type = resume_source_type
    response.resume_strategy = resume_strategy
    response.applied_clarification_fields = applied_clarification_fields
    response.question_rewritten = resumed_question != source_question
    response.overridden_plan_arguments = overridden_plan_arguments
    return _persist_workflow_response(
        response=response,
        resumed_from_question=source_question,
        source_run_id=source_run_id,
    )


def orchestrate_agent_request(
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    resume_context: dict[str, str] | None = None,
    persist_run: bool = True,
) -> AgentWorkflowResponse:
    """Route and execute the next workflow step for an agent request."""
    workflow_started_at = build_utc_timestamp()
    route = route_request(question=question, filename=filename)
    workflow_trace = [
        WorkflowTraceEvent(
            stage="routing",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=f"Request routed to {route.route_type}.",
        )
    ]

    if route.route_type == "knowledge_retrieval":
        if not filename:
            raise ValueError("filename_required_for_knowledge_route")

        try:
            query_response = run_query(
                filename=filename,
                question=question,
                top_k=top_k,
            )
        except (FileNotFoundError, ValueError):
            raise
        except Exception as exc:
            failed_at = build_utc_timestamp()
            failure_message = _format_failure_message(exc)
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="retrieval",
                    status="failed",
                    timestamp=failed_at,
                    detail=f"Knowledge retrieval failed: {failure_message}.",
                )
            )
            response = _build_failed_workflow_response(
                question=question,
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                started_at=workflow_started_at,
                failed_at=failed_at,
                terminal_reason="knowledge_retrieval_failed",
                failure_stage="retrieval",
                failure_message=failure_message,
            )
            return _persist_workflow_response(response) if persist_run else response
        workflow_trace.extend(
            [
                WorkflowTraceEvent(
                    stage="retrieval",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Retrieved {len(query_response.retrieval.matches)} supporting chunks "
                        f"from {query_response.filename}."
                    ),
                ),
                WorkflowTraceEvent(
                    stage="answer_generation",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=f"Answer generated via {query_response.chat_provider}.",
                ),
            ]
        )
        response = AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            route=route,
            workflow_trace=workflow_trace,
            filename=query_response.filename,
            answer=query_response.answer,
            answer_source=query_response.answer_source,
            model=query_response.model,
            answered_at=query_response.answered_at,
            answer_latency_ms=query_response.answer_latency_ms,
            chat_provider=query_response.chat_provider,
            chat_model=query_response.chat_model,
            retrieval=query_response.retrieval,
        )
        response = _finalize_workflow_response(
            response,
            started_at=workflow_started_at,
            terminal_reason="knowledge_answer_generated",
            completed_at=query_response.answered_at,
        )
        return _persist_workflow_response(response) if persist_run else response

    if route.route_type == "tool_execution":
        chained_steps: list[dict] = []
        workflow_kind, workflow_search_question, workflow_follow_up_question, workflow_planning_mode = (
            _resolve_multistep_workflow(question)
        )
        resume_context = resume_context or {}

        if workflow_kind in {"search_then_ticket", "search_then_summarize"}:
            planner_label = _describe_workflow_planning_mode(workflow_planning_mode)
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="workflow_planning",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Planned {workflow_kind} workflow via {planner_label}."
                    ),
                )
            )

        if workflow_kind == "search_then_ticket" and workflow_search_question and workflow_follow_up_question:
            search_question, ticket_question = workflow_search_question, workflow_follow_up_question
            prior_search_context: dict[str, str] = {}
            ticket_resume_overrides = _extract_resume_ticket_overrides(resume_context)
            execution_confirmed = _normalize_confirmation(
                resume_context.get("execution_confirmation", "")
            )

            for step_index, step_question in enumerate((search_question, ticket_question), start=1):
                step_started_at = build_utc_timestamp()
                try:
                    tool_plan = plan_tool_request(step_question)
                except ValueError:
                    raise
                except Exception as exc:
                    failed_at = build_utc_timestamp()
                    failure_message = _format_failure_message(exc)
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="tool_planning",
                            status="failed",
                            timestamp=failed_at,
                            detail=f"Step {step_index}: tool planning failed: {failure_message}.",
                        )
                    )
                    chained_steps.append(
                        _build_failed_workflow_step_record(
                            step_index=step_index,
                            step_question=step_question,
                            started_at=step_started_at,
                            completed_at=failed_at,
                            failure_message=failure_message,
                        )
                    )
                    response = _build_failed_workflow_response(
                        question=question,
                        route=route,
                        workflow_trace=workflow_trace,
                        filename=filename,
                        started_at=workflow_started_at,
                        failed_at=failed_at,
                        terminal_reason="tool_planning_failed",
                        failure_stage="tool_planning",
                        failure_message=failure_message,
                        step_count=len(chained_steps),
                        tool_chain=chained_steps,
                    )
                    return _persist_workflow_response(response) if persist_run else response
                if (
                    step_index == 2
                    and tool_plan.tool_name == "ticketing"
                    and tool_plan.action == "create"
                    and prior_search_context
                ):
                    tool_plan.arguments = {
                        **prior_search_context,
                        **tool_plan.arguments,
                    }
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="tool_context",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail=(
                                "Step 2 inherited supporting search context from step 1 "
                                "before ticket creation."
                            ),
                        )
                    )
                if step_index == 2 and ticket_resume_overrides:
                    tool_plan.arguments = {
                        **tool_plan.arguments,
                        **ticket_resume_overrides,
                    }
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="resume_context",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail="Applied structured clarification fields to ticket execution.",
                        )
                    )
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_planning",
                        status="completed",
                        timestamp=build_utc_timestamp(),
                        detail=(
                            f"Step {step_index}: planned {tool_plan.tool_name}:{tool_plan.action} "
                            f"for {tool_plan.target}."
                        ),
                    )
                )
                try:
                    tool_response = execute_tool_request(
                        ToolExecutionRequest(
                            tool_name=tool_plan.tool_name,
                            action=tool_plan.action,
                            target=tool_plan.target,
                            arguments=tool_plan.arguments,
                        )
                    )
                except ValueError:
                    raise
                except Exception as exc:
                    failed_at = build_utc_timestamp()
                    failure_message = _format_failure_message(exc)
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="tool_execution",
                            status="failed",
                            timestamp=failed_at,
                            detail=(
                                f"Step {step_index}: tool execution failed for "
                                f"{tool_plan.tool_name}:{tool_plan.action}: {failure_message}."
                            ),
                        )
                    )
                    chained_steps.append(
                        _build_failed_workflow_step_record(
                            step_index=step_index,
                            step_question=step_question,
                            started_at=step_started_at,
                            completed_at=failed_at,
                            failure_message=failure_message,
                            tool_plan=tool_plan.model_dump(),
                        )
                    )
                    response = _build_failed_workflow_response(
                        question=question,
                        route=route,
                        workflow_trace=workflow_trace,
                        filename=filename,
                        started_at=workflow_started_at,
                        failed_at=failed_at,
                        terminal_reason="tool_execution_failed",
                        failure_stage="tool_execution",
                        failure_message=failure_message,
                        step_count=len(chained_steps),
                        tool_plan=tool_plan.model_dump(),
                        tool_chain=chained_steps,
                    )
                    return _persist_workflow_response(response) if persist_run else response
                step_completed_at = build_utc_timestamp()
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_execution",
                        status="completed",
                        timestamp=step_completed_at,
                        detail=(
                            f"Step {step_index}: executed {tool_response.execution_mode} tool "
                            f"{tool_response.tool_name}:{tool_response.action} "
                            f"with status {tool_response.execution_status}."
                        ),
                    )
                )
                chained_steps.append(
                    _build_workflow_step_record(
                        step_index=step_index,
                        step_question=step_question,
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response.model_dump(),
                        started_at=step_started_at,
                        completed_at=step_completed_at,
                    )
                )

                if (
                    step_index == 1
                    and tool_response.tool_name == "document_search"
                    and tool_response.output.get("matched_count") == "0"
                ):
                    if execution_confirmed:
                        workflow_trace.append(
                            WorkflowTraceEvent(
                                stage="resume_context",
                                status="completed",
                                timestamp=build_utc_timestamp(),
                                detail=(
                                    "Search returned no supporting documents, but execution continued "
                                    "because the clarified workflow explicitly confirmed proceeding."
                                ),
                            )
                        )
                        prior_search_context = {}
                        continue
                    clarification_plan = plan_search_miss_clarification(
                        search_query=tool_plan.target,
                        next_action_question=ticket_question,
                    )
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="clarification_planning",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail=(
                                "Search produced no supporting documents, so the workflow "
                                "stopped before ticket creation and requested clarification."
                            ),
                        )
                    )
                    response = AgentWorkflowResponse(
                        question=question,
                        workflow_status="clarification_required",
                        route=route,
                        workflow_trace=workflow_trace,
                        filename=filename,
                        clarification_message=(
                            "No supporting documents matched the search step, so the system "
                            "needs clarification before creating a ticket."
                        ),
                        clarification_plan=clarification_plan.model_dump(),
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response.model_dump(),
                        step_count=len(chained_steps),
                        tool_chain=chained_steps,
                    )
                    response = _finalize_workflow_response(
                        response,
                        started_at=workflow_started_at,
                        terminal_reason="search_miss_clarification",
                        last_updated_at=workflow_trace[-1].timestamp,
                    )
                    return _persist_workflow_response(response) if persist_run else response

                if step_index == 1 and tool_response.tool_name == "document_search":
                    prior_search_context = _build_search_context_arguments(tool_response.output)

            final_step = chained_steps[-1]
            response = AgentWorkflowResponse(
                question=question,
                workflow_status="completed",
                step_count=len(chained_steps),
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                tool_plan=final_step["tool_plan"],
                tool_execution=final_step["tool_execution"],
                tool_chain=chained_steps,
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="tool_execution_completed",
                completed_at=workflow_trace[-1].timestamp,
            )
            return _persist_workflow_response(response) if persist_run else response

        if workflow_kind == "search_then_summarize" and workflow_search_question and workflow_follow_up_question:
            search_question, summarize_question = workflow_search_question, workflow_follow_up_question
            step_started_at = build_utc_timestamp()
            try:
                tool_plan = plan_tool_request(search_question)
            except ValueError:
                raise
            except Exception as exc:
                failed_at = build_utc_timestamp()
                failure_message = _format_failure_message(exc)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_planning",
                        status="failed",
                        timestamp=failed_at,
                        detail=f"Tool planning failed: {failure_message}.",
                    )
                )
                chained_steps.append(
                    _build_failed_workflow_step_record(
                        step_index=1,
                        step_question=search_question,
                        started_at=step_started_at,
                        completed_at=failed_at,
                        failure_message=failure_message,
                    )
                )
                response = _build_failed_workflow_response(
                    question=question,
                    route=route,
                    workflow_trace=workflow_trace,
                    filename=filename,
                    started_at=workflow_started_at,
                    failed_at=failed_at,
                    terminal_reason="tool_planning_failed",
                    failure_stage="tool_planning",
                    failure_message=failure_message,
                    step_count=1,
                    tool_chain=chained_steps,
                )
                return _persist_workflow_response(response) if persist_run else response
            summary_context = _extract_summary_step_context(summarize_question)
            if summary_context:
                tool_plan.arguments = {
                    **tool_plan.arguments,
                    **summary_context,
                }
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_planning",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Planned {tool_plan.tool_name}:{tool_plan.action} for "
                        f"{tool_plan.target}."
                    ),
                )
            )
            try:
                tool_response = execute_tool_request(
                    ToolExecutionRequest(
                        tool_name=tool_plan.tool_name,
                        action=tool_plan.action,
                        target=tool_plan.target,
                        arguments=tool_plan.arguments,
                    )
                )
            except ValueError:
                raise
            except Exception as exc:
                failed_at = build_utc_timestamp()
                failure_message = _format_failure_message(exc)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_execution",
                        status="failed",
                        timestamp=failed_at,
                        detail=(
                            f"Tool execution failed for {tool_plan.tool_name}:{tool_plan.action}: "
                            f"{failure_message}."
                        ),
                    )
                )
                chained_steps.append(
                    _build_failed_workflow_step_record(
                        step_index=1,
                        step_question=search_question,
                        started_at=step_started_at,
                        completed_at=failed_at,
                        failure_message=failure_message,
                        tool_plan=tool_plan.model_dump(),
                    )
                )
                response = _build_failed_workflow_response(
                    question=question,
                    route=route,
                    workflow_trace=workflow_trace,
                    filename=filename,
                    started_at=workflow_started_at,
                    failed_at=failed_at,
                    terminal_reason="tool_execution_failed",
                    failure_stage="tool_execution",
                    failure_message=failure_message,
                    step_count=1,
                    tool_plan=tool_plan.model_dump(),
                    tool_chain=chained_steps,
                )
                return _persist_workflow_response(response) if persist_run else response
            step_completed_at = build_utc_timestamp()
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_execution",
                    status="completed",
                    timestamp=step_completed_at,
                    detail=(
                        f"Executed {tool_response.execution_mode} tool "
                        f"{tool_response.tool_name}:{tool_response.action} "
                        f"with status {tool_response.execution_status}."
                    ),
                )
            )
            chained_steps.append(
                _build_workflow_step_record(
                    step_index=1,
                    step_question=search_question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                )
            )

            if tool_response.output.get("matched_count") == "0":
                clarification_plan = plan_search_summary_miss_clarification(tool_plan.target)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="clarification_planning",
                        status="completed",
                        timestamp=build_utc_timestamp(),
                        detail=(
                            "Search produced no supporting documents, so the workflow "
                            "stopped before summary generation and requested clarification."
                        ),
                    )
                )
                response = AgentWorkflowResponse(
                    question=question,
                    workflow_status="clarification_required",
                    route=route,
                    workflow_trace=workflow_trace,
                    filename=filename,
                    clarification_message=(
                        "No supporting documents matched the search step, so the system "
                        "needs clarification before generating a summary."
                    ),
                    clarification_plan=clarification_plan.model_dump(),
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    step_count=len(chained_steps),
                    tool_chain=chained_steps,
                )
                response = _finalize_workflow_response(
                    response,
                    started_at=workflow_started_at,
                    terminal_reason="search_summary_miss_clarification",
                    last_updated_at=workflow_trace[-1].timestamp,
                )
                return _persist_workflow_response(response) if persist_run else response

            try:
                summary_answer = _build_search_summary(tool_response.output)
            except Exception as exc:
                failed_at = build_utc_timestamp()
                failure_message = _format_failure_message(exc)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="search_summary",
                        status="failed",
                        timestamp=failed_at,
                        detail=f"Search summary generation failed: {failure_message}.",
                    )
                )
                response = _build_failed_workflow_response(
                    question=question,
                    route=route,
                    workflow_trace=workflow_trace,
                    filename=filename,
                    started_at=workflow_started_at,
                    failed_at=failed_at,
                    terminal_reason="search_summary_failed",
                    failure_stage="search_summary",
                    failure_message=failure_message,
                    step_count=len(chained_steps),
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    tool_chain=chained_steps,
                )
                return _persist_workflow_response(response) if persist_run else response
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="search_summary",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Generated a local summary for search results in response to "
                        f"'{summarize_question}'."
                    ),
                )
            )
            answered_at = build_utc_timestamp()
            response = AgentWorkflowResponse(
                question=question,
                workflow_status="completed",
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                answer=summary_answer,
                answer_source="local_search_summary",
                model="local-heuristic-summary",
                answered_at=answered_at,
                answer_latency_ms=0.0,
                chat_provider="local",
                chat_model="local-heuristic-summary",
                tool_plan=tool_plan.model_dump(),
                tool_execution=tool_response.model_dump(),
                step_count=len(chained_steps),
                tool_chain=chained_steps,
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="search_summary_completed",
                completed_at=answered_at,
            )
            return _persist_workflow_response(response) if persist_run else response

        step_started_at = build_utc_timestamp()
        try:
            tool_plan = plan_tool_request(question)
        except ValueError:
            raise
        except Exception as exc:
            failed_at = build_utc_timestamp()
            failure_message = _format_failure_message(exc)
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_planning",
                    status="failed",
                    timestamp=failed_at,
                    detail=f"Tool planning failed: {failure_message}.",
                )
            )
            failed_step = _build_failed_workflow_step_record(
                step_index=1,
                step_question=question,
                started_at=step_started_at,
                completed_at=failed_at,
                failure_message=failure_message,
            )
            response = _build_failed_workflow_response(
                question=question,
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                started_at=workflow_started_at,
                failed_at=failed_at,
                terminal_reason="tool_planning_failed",
                failure_stage="tool_planning",
                failure_message=failure_message,
                step_count=1,
                tool_chain=[failed_step],
            )
            return _persist_workflow_response(response) if persist_run else response
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_planning",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail=(
                    f"Planned {tool_plan.tool_name}:{tool_plan.action} for "
                    f"{tool_plan.target}."
                ),
            )
        )
        if _requires_unsupported_action_clarification(question):
            clarification_plan = plan_unsupported_action_clarification(question, tool_plan.target)
            fallback_tool_plan = _build_unsupported_action_fallback_plan(question, tool_plan.target)
            clarification_timestamp = build_utc_timestamp()
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="clarification_planning",
                    status="completed",
                    timestamp=clarification_timestamp,
                    detail=(
                        "The request requires an unsupported direct operational action, "
                        "so the workflow requested clarification before falling back to ticket creation."
                    ),
                )
            )
            response = AgentWorkflowResponse(
                question=question,
                workflow_status="clarification_required",
                step_count=0,
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                clarification_message=clarification_plan.clarification_summary,
                clarification_plan=clarification_plan.model_dump(),
                tool_plan=fallback_tool_plan,
                tool_chain=[],
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="unsupported_action_clarification",
                last_updated_at=clarification_timestamp,
            )
            return _persist_workflow_response(response) if persist_run else response
        try:
            tool_response = execute_tool_request(
                ToolExecutionRequest(
                    tool_name=tool_plan.tool_name,
                    action=tool_plan.action,
                    target=tool_plan.target,
                    arguments=tool_plan.arguments,
                )
            )
        except ValueError:
            raise
        except Exception as exc:
            failed_at = build_utc_timestamp()
            failure_message = _format_failure_message(exc)
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_execution",
                    status="failed",
                    timestamp=failed_at,
                    detail=(
                        f"Tool execution failed for {tool_plan.tool_name}:{tool_plan.action}: "
                        f"{failure_message}."
                    ),
                )
            )
            failed_step = _build_failed_workflow_step_record(
                step_index=1,
                step_question=question,
                started_at=step_started_at,
                completed_at=failed_at,
                failure_message=failure_message,
                tool_plan=tool_plan.model_dump(),
            )
            response = _build_failed_workflow_response(
                question=question,
                route=route,
                workflow_trace=workflow_trace,
                filename=filename,
                started_at=workflow_started_at,
                failed_at=failed_at,
                terminal_reason="tool_execution_failed",
                failure_stage="tool_execution",
                failure_message=failure_message,
                step_count=1,
                tool_plan=tool_plan.model_dump(),
                tool_chain=[failed_step],
            )
            return _persist_workflow_response(response) if persist_run else response
        step_completed_at = build_utc_timestamp()
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_execution",
                status="completed",
                timestamp=step_completed_at,
                detail=(
                    f"Executed {tool_response.execution_mode} tool "
                    f"{tool_response.tool_name}:{tool_response.action} "
                    f"with status {tool_response.execution_status}."
                ),
            )
        )
        response = AgentWorkflowResponse(
            question=question,
            workflow_status="completed",
            step_count=1,
            route=route,
            workflow_trace=workflow_trace,
            filename=filename,
            tool_plan=tool_plan.model_dump(),
            tool_execution=tool_response.model_dump(),
            tool_chain=[
                _build_workflow_step_record(
                    step_index=1,
                    step_question=question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response.model_dump(),
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                )
            ],
        )
        response = _finalize_workflow_response(
            response,
            started_at=workflow_started_at,
            terminal_reason="tool_execution_completed",
            completed_at=step_completed_at,
        )
        return _persist_workflow_response(response) if persist_run else response

    clarification_plan = plan_clarification(question)
    workflow_trace.append(
        WorkflowTraceEvent(
            stage="clarification_planning",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=(
                f"Clarification requested for fields: "
                f"{', '.join(clarification_plan.missing_fields)}."
            ),
        )
    )
    response = AgentWorkflowResponse(
        question=question,
        workflow_status="clarification_required",
        step_count=0,
        route=route,
        workflow_trace=workflow_trace,
        filename=filename,
        clarification_message=clarification_plan.clarification_summary,
        clarification_plan=clarification_plan.model_dump(),
        tool_chain=[],
    )
    response = _finalize_workflow_response(
        response,
        started_at=workflow_started_at,
        terminal_reason="clarification_requested",
        last_updated_at=workflow_trace[-1].timestamp,
    )
    return _persist_workflow_response(response) if persist_run else response
