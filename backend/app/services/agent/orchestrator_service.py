import json
import re
import time
import uuid

from app.core.config import DATA_ROOT
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

WORKFLOW_RUN_DATA_DIR = DATA_ROOT / "tool_state"
WORKFLOW_RUN_DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOW_RUN_STORE_PATH = WORKFLOW_RUN_DATA_DIR / "workflow_runs.json"

SEARCH_AND_TICKET_PATTERN = re.compile(
    r"(?P<search>^(?:search|find|lookup|look up).+?)(?:\s+and\s+|\s*,?\s+then\s+)(?P<ticket>(?:create|open|update|close).+\bticket\b.+)$",
    re.IGNORECASE,
)
SEARCH_AND_SUMMARIZE_PATTERN = re.compile(
    r"(?P<search>^(?:search|find|lookup|look up).+?)(?:\s+and\s+|\s*,?\s+then\s+)(?P<summarize>summari[sz]e.+)$",
    re.IGNORECASE,
)
STATUS_AND_SUMMARIZE_PATTERN = re.compile(
    r"(?P<status>^(?:check|show|inspect|query).+?\b(?:status|health|configuration|config)\b.+?)(?:\s+and\s+|\s*,?\s+then\s+)(?P<summarize>summari[sz]e.+)$",
    re.IGNORECASE,
)
STATUS_AND_TICKET_PATTERN = re.compile(
    r"(?P<status>^(?:check|show|inspect|query).+?\b(?:status|health|configuration|config)\b.+?)(?:\s+and\s+|\s*,?\s+then\s+)(?P<ticket>(?:create|open|update|close).+\bticket\b.+)$",
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
MAX_TOOL_EXECUTION_RETRIES = 1


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
            normalized_step.setdefault("attempt_count", 1)
            normalized_step.setdefault("retried", False)
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
                "attempt_count": 1,
                "retried": False,
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
    run_id = normalized_run.get("run_id")
    source_run_id = normalized_run.get("source_run_id")
    root_run_id = normalized_run.get("root_run_id")
    normalized_run["root_run_id"] = (
        root_run_id.strip()
        if isinstance(root_run_id, str) and root_run_id.strip()
        else source_run_id.strip()
        if isinstance(source_run_id, str) and source_run_id.strip()
        else run_id.strip()
        if isinstance(run_id, str) and run_id.strip()
        else None
    )
    recovery_depth = normalized_run.get("recovery_depth")
    normalized_run["recovery_depth"] = (
        recovery_depth
        if isinstance(recovery_depth, int) and recovery_depth >= 0
        else 1
        if isinstance(source_run_id, str) and source_run_id.strip()
        else 0
    )
    recovered_via_action = normalized_run.get("recovered_via_action")
    normalized_run["recovered_via_action"] = (
        recovered_via_action.strip()
        if isinstance(recovered_via_action, str) and recovered_via_action.strip()
        else None
    )
    normalized_run["tool_chain"] = _normalize_persisted_workflow_step_records(normalized_run)
    resumed_from_step_index = normalized_run.get("resumed_from_step_index")
    normalized_run["resumed_from_step_index"] = (
        resumed_from_step_index
        if isinstance(resumed_from_step_index, int) and resumed_from_step_index > 0
        else None
    )
    existing_reused_step_indices = normalized_run.get("reused_step_indices")
    if isinstance(existing_reused_step_indices, list):
        normalized_run["reused_step_indices"] = [
            step for step in existing_reused_step_indices if isinstance(step, int) and step > 0
        ]
    else:
        normalized_run["reused_step_indices"] = []
    normalized_run["step_count"] = _backfill_step_count(normalized_run)
    normalized_run["started_at"] = _backfill_started_at(normalized_run)
    normalized_run["completed_at"] = _backfill_completed_at(normalized_run)
    normalized_run["last_updated_at"] = _backfill_last_updated_at(normalized_run)
    normalized_run["terminal_reason"] = _backfill_terminal_reason(normalized_run)
    normalized_run["outcome_category"] = (
        normalized_run.get("outcome_category")
        or _derive_outcome_category(normalized_run)
    )
    normalized_run["is_recoverable"] = _backfill_is_recoverable(normalized_run)
    normalized_run["retry_count"] = _backfill_retry_count(normalized_run)
    normalized_run["retried_step_indices"] = _backfill_retried_step_indices(normalized_run)
    normalized_run["retry_state"] = (
        normalized_run.get("retry_state")
        or _derive_retry_state(normalized_run)
    )
    normalized_run["recommended_recovery_action"] = (
        normalized_run.get("recommended_recovery_action")
        or _derive_recommended_recovery_action(normalized_run)
    )
    existing_available_recovery_actions = normalized_run.get("available_recovery_actions")
    if isinstance(existing_available_recovery_actions, list):
        normalized_run["available_recovery_actions"] = [
            action.strip()
            for action in existing_available_recovery_actions
            if isinstance(action, str) and action.strip()
        ]
    else:
        normalized_run["available_recovery_actions"] = _derive_available_recovery_actions(normalized_run)
    existing_recovery_action_details = normalized_run.get("recovery_action_details")
    if isinstance(existing_recovery_action_details, dict):
        normalized_run["recovery_action_details"] = {
            action: detail
            for action, detail in existing_recovery_action_details.items()
            if isinstance(action, str) and action.strip() and isinstance(detail, dict)
        }
    else:
        normalized_run["recovery_action_details"] = _derive_recovery_action_details(normalized_run)
    normalized_run["workflow_planning_mode"] = (
        normalized_run.get("workflow_planning_mode")
        or _extract_workflow_planning_mode_from_trace(normalized_run.get("workflow_trace", []))
    )
    normalized_run["tool_planning_mode"] = (
        normalized_run.get("tool_planning_mode")
        or _extract_tool_planning_mode(normalized_run)
    )
    existing_tool_planning_modes = normalized_run.get("tool_planning_modes")
    if isinstance(existing_tool_planning_modes, list):
        normalized_run["tool_planning_modes"] = [
            mode.strip()
            for mode in existing_tool_planning_modes
            if isinstance(mode, str) and mode.strip()
        ]
    else:
        normalized_run["tool_planning_modes"] = _extract_tool_planning_modes(normalized_run)
    normalized_run["clarification_planning_mode"] = (
        normalized_run.get("clarification_planning_mode")
        or _extract_clarification_planning_mode(normalized_run)
    )
    normalized_run["tool_planner_call_count"] = _coerce_non_negative_int(
        normalized_run.get("tool_planner_call_count")
    ) or len(normalized_run["tool_planning_modes"])
    existing_llm_tool_planner_steps = normalized_run.get("llm_tool_planner_steps")
    if isinstance(existing_llm_tool_planner_steps, list):
        normalized_run["llm_tool_planner_steps"] = [
            step for step in existing_llm_tool_planner_steps if isinstance(step, int) and step > 0
        ]
    else:
        normalized_run["llm_tool_planner_steps"] = _extract_tool_planner_steps_by_mode(
            normalized_run["tool_planning_modes"],
            llm_only=True,
        )
    existing_fallback_tool_planner_steps = normalized_run.get("fallback_tool_planner_steps")
    if isinstance(existing_fallback_tool_planner_steps, list):
        normalized_run["fallback_tool_planner_steps"] = [
            step for step in existing_fallback_tool_planner_steps if isinstance(step, int) and step > 0
        ]
    else:
        normalized_run["fallback_tool_planner_steps"] = _extract_tool_planner_steps_by_mode(
            normalized_run["tool_planning_modes"],
            llm_only=False,
        )
    normalized_run["workflow_planning_latency_ms"] = _coerce_non_negative_int(
        normalized_run.get("workflow_planning_latency_ms")
    )
    normalized_run["tool_planning_latency_ms"] = _coerce_non_negative_int(
        normalized_run.get("tool_planning_latency_ms")
    )
    normalized_run["clarification_planning_latency_ms"] = _coerce_non_negative_int(
        normalized_run.get("clarification_planning_latency_ms")
    )
    normalized_run["planner_latency_ms_total"] = _coerce_non_negative_int(
        normalized_run.get("planner_latency_ms_total")
    ) or (
        normalized_run["workflow_planning_latency_ms"]
        + normalized_run["tool_planning_latency_ms"]
        + normalized_run["clarification_planning_latency_ms"]
    )
    normalized_run["planner_call_count"] = _coerce_non_negative_int(
        normalized_run.get("planner_call_count")
    ) or (
        (1 if normalized_run["workflow_planning_mode"] else 0)
        + normalized_run["tool_planner_call_count"]
        + (1 if normalized_run["clarification_planning_mode"] else 0)
    )
    existing_llm_planner_layers = normalized_run.get("llm_planner_layers")
    if isinstance(existing_llm_planner_layers, list):
        normalized_run["llm_planner_layers"] = [
            layer.strip()
            for layer in existing_llm_planner_layers
            if isinstance(layer, str) and layer.strip()
        ]
    else:
        normalized_run["llm_planner_layers"] = [
            layer
            for layer, mode in (
                ("workflow", normalized_run["workflow_planning_mode"]),
                ("tool", normalized_run["tool_planning_mode"]),
                ("clarification", normalized_run["clarification_planning_mode"]),
            )
            if isinstance(mode, str)
            and mode.startswith("llm_")
            and (layer != "tool" or bool(normalized_run["llm_tool_planner_steps"]))
        ]
    existing_fallback_planner_layers = normalized_run.get("fallback_planner_layers")
    if isinstance(existing_fallback_planner_layers, list):
        normalized_run["fallback_planner_layers"] = [
            layer.strip()
            for layer in existing_fallback_planner_layers
            if isinstance(layer, str) and layer.strip()
        ]
    else:
        normalized_run["fallback_planner_layers"] = [
            layer
            for layer, mode in (
                ("workflow", normalized_run["workflow_planning_mode"]),
                ("tool", normalized_run["tool_planning_mode"]),
                ("clarification", normalized_run["clarification_planning_mode"]),
            )
            if isinstance(mode, str)
            and not mode.startswith("llm_")
            and mode != "heuristic workflow matcher"
            and (layer != "tool" or bool(normalized_run["fallback_tool_planner_steps"]))
        ]
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


def _derive_outcome_category(response: AgentWorkflowResponse | dict) -> str | None:
    workflow_status = (
        response.workflow_status if isinstance(response, AgentWorkflowResponse) else response.get("workflow_status")
    )
    terminal_reason = (
        response.terminal_reason if isinstance(response, AgentWorkflowResponse) else response.get("terminal_reason")
    )

    if workflow_status == "completed":
        return "completed"
    if workflow_status == "clarification_required":
        return "clarification_required"
    if workflow_status == "failed":
        if isinstance(terminal_reason, str) and terminal_reason in {
            "knowledge_retrieval_failed",
            "tool_planning_failed",
            "tool_execution_failed",
            "search_summary_failed",
            "status_summary_failed",
        }:
            return "recoverable_failure"
        return "non_recoverable_failure"
    return None


def _derive_is_recoverable(response: AgentWorkflowResponse | dict) -> bool | None:
    outcome_category = _derive_outcome_category(response)
    if outcome_category == "completed":
        return False
    if outcome_category == "clarification_required":
        return True
    if outcome_category == "recoverable_failure":
        return True
    if outcome_category == "non_recoverable_failure":
        return False
    return None


def _backfill_is_recoverable(run: dict) -> bool | None:
    existing = run.get("is_recoverable")
    if isinstance(existing, bool):
        return existing
    return _derive_is_recoverable(run)


def _derive_retry_state(response: AgentWorkflowResponse | dict) -> str | None:
    workflow_status = (
        response.workflow_status if isinstance(response, AgentWorkflowResponse) else response.get("workflow_status")
    )
    outcome_category = _derive_outcome_category(response)
    failure_stage = (
        response.failure_stage if isinstance(response, AgentWorkflowResponse) else response.get("failure_stage")
    )
    retry_count = (
        response.retry_count if isinstance(response, AgentWorkflowResponse) else response.get("retry_count")
    )
    retry_count = retry_count if isinstance(retry_count, int) and retry_count >= 0 else 0

    if workflow_status in {"completed", "clarification_required"}:
        return "not_applicable"

    if outcome_category != "recoverable_failure":
        return "not_applicable"

    if failure_stage == "tool_execution" and retry_count >= MAX_TOOL_EXECUTION_RETRIES:
        return "retry_exhausted"

    return "retry_available"


def _is_failed_step_resume_eligible(response: AgentWorkflowResponse | dict) -> bool:
    if isinstance(response, AgentWorkflowResponse):
        workflow_status = response.workflow_status
        failure_stage = response.failure_stage
        question = response.question
        tool_chain = response.tool_chain
    else:
        workflow_status = response.get("workflow_status")
        failure_stage = response.get("failure_stage")
        question = response.get("question", "")
        tool_chain = response.get("tool_chain", [])

    if workflow_status != "failed":
        return False
    if not isinstance(question, str) or not question.strip():
        return False
    if not isinstance(tool_chain, list) or not tool_chain:
        return False

    workflow_kind, _, _, _ = _resolve_multistep_workflow(question)

    def _step_value(step: object, field: str):
        if isinstance(step, dict):
            return step.get(field)
        return getattr(step, field, None)

    reusable_step = tool_chain[0]

    if workflow_kind in {"search_then_ticket", "status_then_ticket"}:
        if failure_stage != "tool_execution" or len(tool_chain) < 2:
            return False
        failed_step = tool_chain[-1]
        return (
            _step_value(reusable_step, "step_index") == 1
            and _step_value(reusable_step, "step_status") == "completed"
            and _step_value(failed_step, "step_index") == 2
            and _step_value(failed_step, "step_status") == "failed"
        )

    if workflow_kind in {"search_then_summarize", "status_then_summarize"}:
        return (
            failure_stage in {"search_summary", "status_summary"}
            and _step_value(reusable_step, "step_index") == 1
            and _step_value(reusable_step, "step_status") == "completed"
        )

    return False


def _derive_recommended_recovery_action(response: AgentWorkflowResponse | dict) -> str | None:
    outcome_category = _derive_outcome_category(response)
    retry_state = _derive_retry_state(response)
    if outcome_category == "completed":
        return "none"
    if outcome_category == "clarification_required":
        return "resume_with_clarification"
    if outcome_category == "recoverable_failure":
        if _is_failed_step_resume_eligible(response):
            return "resume_from_failed_step"
        if retry_state == "retry_exhausted":
            return "manual_retrigger"
        return "retry"
    if outcome_category == "non_recoverable_failure":
        return "manual_investigation"
    return None


def _derive_available_recovery_actions(response: AgentWorkflowResponse | dict) -> list[str]:
    outcome_category = _derive_outcome_category(response)
    retry_state = _derive_retry_state(response)
    if outcome_category == "completed":
        return []
    if outcome_category == "clarification_required":
        return ["resume_with_clarification"]
    if outcome_category == "recoverable_failure":
        if _is_failed_step_resume_eligible(response):
            return ["resume_from_failed_step", "manual_retrigger"]
        if retry_state == "retry_exhausted":
            return ["manual_retrigger"]
        return ["retry"]
    if outcome_category == "non_recoverable_failure":
        return ["manual_investigation"]
    return []


def _derive_failed_step_resume_details(response: AgentWorkflowResponse | dict) -> dict[str, object]:
    if not _is_failed_step_resume_eligible(response):
        return {}

    if isinstance(response, AgentWorkflowResponse):
        question = response.question
        tool_chain = response.tool_chain
    else:
        question = response.get("question", "")
        tool_chain = response.get("tool_chain", [])

    workflow_kind, _, _, _ = _resolve_multistep_workflow(question)

    def _step_value(step: object, field: str):
        if isinstance(step, dict):
            return step.get(field)
        return getattr(step, field, None)

    target_step_index = 2
    if workflow_kind in {"search_then_ticket", "status_then_ticket"} and isinstance(tool_chain, list) and tool_chain:
        last_step = tool_chain[-1]
        step_index = _step_value(last_step, "step_index")
        if isinstance(step_index, int) and step_index > 0:
            target_step_index = step_index

    return {
        "workflow_kind": workflow_kind,
        "target_step_index": target_step_index,
        "reused_step_indices": [1],
    }


def _derive_recovery_action_details(response: AgentWorkflowResponse | dict) -> dict[str, dict[str, object]]:
    available_actions = _derive_available_recovery_actions(response)
    details: dict[str, dict[str, object]] = {}

    if "resume_from_failed_step" in available_actions:
        details["resume_from_failed_step"] = _derive_failed_step_resume_details(response)

    if "resume_with_clarification" in available_actions:
        clarification_plan = (
            response.clarification_plan
            if isinstance(response, AgentWorkflowResponse)
            else response.get("clarification_plan")
        )
        missing_fields = []
        if isinstance(clarification_plan, dict):
            raw_missing_fields = clarification_plan.get("missing_fields")
            if isinstance(raw_missing_fields, list):
                missing_fields = [field for field in raw_missing_fields if isinstance(field, str)]
        details["resume_with_clarification"] = {
            "missing_fields": missing_fields,
        }

    if "manual_retrigger" in available_actions:
        details["manual_retrigger"] = {
            "restarts_workflow": True,
        }

    if "retry" in available_actions:
        details["retry"] = {
            "retries_from_start": True,
        }

    if "manual_investigation" in available_actions:
        failure_stage = (
            response.failure_stage
            if isinstance(response, AgentWorkflowResponse)
            else response.get("failure_stage")
        )
        details["manual_investigation"] = {
            "requires_manual_review": True,
            "failure_stage": failure_stage,
        }

    return details


def _coerce_non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _step_attempt_count(step: dict) -> int:
    value = step.get("attempt_count")
    return value if isinstance(value, int) and value > 0 else 1


def _backfill_retry_count(run: dict) -> int:
    existing = run.get("retry_count")
    if isinstance(existing, int) and existing >= 0:
        return existing
    return sum(max(0, _step_attempt_count(step) - 1) for step in _tool_chain_step_records(run))


def _backfill_retried_step_indices(run: dict) -> list[int]:
    existing = run.get("retried_step_indices")
    if isinstance(existing, list):
        return [value for value in existing if isinstance(value, int) and value > 0]

    retried_steps: list[int] = []
    for step in _tool_chain_step_records(run):
        if _step_attempt_count(step) > 1:
            step_index = step.get("step_index")
            if isinstance(step_index, int) and step_index > 0:
                retried_steps.append(step_index)
    return retried_steps


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _workflow_run_requires_migration(run: dict) -> bool:
    normalized_run = _normalize_persisted_workflow_run(run)
    migration_fields = (
        "root_run_id",
        "recovery_depth",
        "tool_chain",
        "step_count",
        "started_at",
        "completed_at",
        "last_updated_at",
        "terminal_reason",
        "outcome_category",
        "is_recoverable",
        "recovered_via_action",
        "retry_state",
        "recommended_recovery_action",
        "available_recovery_actions",
        "recovery_action_details",
        "retry_count",
        "retried_step_indices",
        "workflow_planning_mode",
        "tool_planning_mode",
        "tool_planning_modes",
        "clarification_planning_mode",
        "planner_call_count",
        "tool_planner_call_count",
        "workflow_planning_latency_ms",
        "tool_planning_latency_ms",
        "clarification_planning_latency_ms",
        "planner_latency_ms_total",
        "llm_planner_layers",
        "fallback_planner_layers",
        "llm_tool_planner_steps",
        "fallback_tool_planner_steps",
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
    tool_planning_modes = _extract_tool_planning_modes(response)
    if tool_planning_modes:
        return tool_planning_modes[-1]

    if isinstance(response, AgentWorkflowResponse):
        tool_plan = response.tool_plan
    else:
        tool_plan = response.get("tool_plan")

    if isinstance(tool_plan, dict):
        planning_mode = tool_plan.get("planning_mode")
        if isinstance(planning_mode, str) and planning_mode.strip():
            return planning_mode
    return None


def _extract_tool_planning_modes(response: AgentWorkflowResponse | dict) -> list[str]:
    if isinstance(response, AgentWorkflowResponse):
        tool_chain = response.tool_chain
        tool_plan = response.tool_plan
    else:
        tool_chain = response.get("tool_chain")
        tool_plan = response.get("tool_plan")
    tool_planning_modes: list[str] = []

    if isinstance(tool_chain, list):
        for step in tool_chain:
            if isinstance(step, dict):
                step_tool_plan = step.get("tool_plan")
            else:
                step_tool_plan = step.tool_plan
            if isinstance(step_tool_plan, dict):
                planning_mode = step_tool_plan.get("planning_mode")
                if isinstance(planning_mode, str) and planning_mode.strip():
                    tool_planning_modes.append(planning_mode.strip())

    if tool_planning_modes:
        return tool_planning_modes

    if isinstance(tool_plan, dict):
        planning_mode = tool_plan.get("planning_mode")
        if isinstance(planning_mode, str) and planning_mode.strip():
            return [planning_mode.strip()]

    return tool_planning_modes


def _extract_tool_planner_steps_by_mode(tool_planning_modes: list[str], *, llm_only: bool) -> list[int]:
    matching_steps: list[int] = []
    for index, planning_mode in enumerate(tool_planning_modes, start=1):
        if llm_only and planning_mode.startswith("llm_"):
            matching_steps.append(index)
        if not llm_only and not planning_mode.startswith("llm_"):
            matching_steps.append(index)
    return matching_steps


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
    response.outcome_category = _derive_outcome_category(response)
    response.is_recoverable = _derive_is_recoverable(response)
    response.retry_count = sum(
        max(0, getattr(step, "attempt_count", 1) - 1) for step in response.tool_chain
    )
    response.retried_step_indices = [
        step.step_index for step in response.tool_chain if getattr(step, "attempt_count", 1) > 1
    ]
    response.retry_state = _derive_retry_state(response)
    response.recommended_recovery_action = _derive_recommended_recovery_action(response)
    response.available_recovery_actions = _derive_available_recovery_actions(response)
    response.recovery_action_details = _derive_recovery_action_details(response)
    response.workflow_planning_mode = _extract_workflow_planning_mode_from_trace(response.workflow_trace)
    response.tool_planning_modes = _extract_tool_planning_modes(response)
    response.tool_planning_mode = _extract_tool_planning_mode(response)
    response.clarification_planning_mode = _extract_clarification_planning_mode(response)
    response.tool_planner_call_count = len(response.tool_planning_modes)
    response.workflow_planning_latency_ms = _coerce_non_negative_int(response.workflow_planning_latency_ms)
    response.tool_planning_latency_ms = _coerce_non_negative_int(response.tool_planning_latency_ms)
    response.clarification_planning_latency_ms = _coerce_non_negative_int(
        response.clarification_planning_latency_ms
    )
    planner_layers = {
        "workflow": response.workflow_planning_mode,
        "tool": response.tool_planning_mode,
        "clarification": response.clarification_planning_mode,
    }
    response.planner_call_count = (
        (1 if response.workflow_planning_mode else 0)
        + response.tool_planner_call_count
        + (1 if response.clarification_planning_mode else 0)
    )
    response.planner_latency_ms_total = (
        response.workflow_planning_latency_ms
        + response.tool_planning_latency_ms
        + response.clarification_planning_latency_ms
    )
    response.llm_tool_planner_steps = _extract_tool_planner_steps_by_mode(
        response.tool_planning_modes,
        llm_only=True,
    )
    response.fallback_tool_planner_steps = _extract_tool_planner_steps_by_mode(
        response.tool_planning_modes,
        llm_only=False,
    )
    response.llm_planner_layers = [
        layer
        for layer, mode in planner_layers.items()
        if (
            isinstance(mode, str)
            and mode.startswith("llm_")
            and (
                layer != "tool"
                or bool(response.llm_tool_planner_steps)
            )
        )
    ]
    response.fallback_planner_layers = [
        layer
        for layer, mode in planner_layers.items()
        if (
            isinstance(mode, str)
            and not mode.startswith("llm_")
            and mode != "heuristic workflow matcher"
            and (
                layer != "tool"
                or bool(response.fallback_tool_planner_steps)
            )
        )
    ]
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
    if source_run_id:
        source_run = next(
            (
                AgentWorkflowResponse.model_validate(_normalize_persisted_workflow_run(run))
                for run in reversed(runs)
                if run.get("run_id") == source_run_id
            ),
            None,
        )
        if source_run:
            response.root_run_id = source_run.root_run_id or source_run.run_id
            response.recovery_depth = source_run.recovery_depth + 1
        else:
            response.root_run_id = source_run_id
            response.recovery_depth = 1
    else:
        response.root_run_id = response.run_id
        response.recovery_depth = 0
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
    workflow_planning_latency_ms: int = 0,
    tool_planning_latency_ms: int = 0,
    clarification_planning_latency_ms: int = 0,
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
        workflow_planning_latency_ms=workflow_planning_latency_ms,
        tool_planning_latency_ms=tool_planning_latency_ms,
        clarification_planning_latency_ms=clarification_planning_latency_ms,
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
                root_run_id=run.root_run_id,
                recovery_depth=run.recovery_depth,
                question=run.question,
                resumed_from_question=run.resumed_from_question,
                source_run_id=run.source_run_id,
                recovered_via_action=run.recovered_via_action,
                resume_source_type=run.resume_source_type,
                resume_strategy=run.resume_strategy,
                resumed_from_step_index=run.resumed_from_step_index,
                reused_step_indices=run.reused_step_indices,
                applied_clarification_fields=run.applied_clarification_fields,
                question_rewritten=run.question_rewritten,
                overridden_plan_arguments=run.overridden_plan_arguments,
                workflow_status=run.workflow_status,
                terminal_reason=run.terminal_reason,
                outcome_category=run.outcome_category,
                is_recoverable=run.is_recoverable,
                retry_state=run.retry_state,
                recommended_recovery_action=run.recommended_recovery_action,
                available_recovery_actions=run.available_recovery_actions,
                recovery_action_details=run.recovery_action_details,
                failure_stage=run.failure_stage,
                failure_message=run.failure_message,
                started_at=run.started_at,
                completed_at=run.completed_at,
                last_updated_at=run.last_updated_at,
                workflow_planning_mode=run.workflow_planning_mode,
                tool_planning_mode=run.tool_planning_mode,
                tool_planning_modes=run.tool_planning_modes,
                clarification_planning_mode=run.clarification_planning_mode,
                planner_call_count=run.planner_call_count,
                tool_planner_call_count=run.tool_planner_call_count,
                workflow_planning_latency_ms=run.workflow_planning_latency_ms,
                tool_planning_latency_ms=run.tool_planning_latency_ms,
                clarification_planning_latency_ms=run.clarification_planning_latency_ms,
                planner_latency_ms_total=run.planner_latency_ms_total,
                llm_planner_layers=run.llm_planner_layers,
                fallback_planner_layers=run.fallback_planner_layers,
                llm_tool_planner_steps=run.llm_tool_planner_steps,
                fallback_tool_planner_steps=run.fallback_tool_planner_steps,
                retry_count=run.retry_count,
                retried_step_indices=run.retried_step_indices,
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
    persisted_runs = get_all_persisted_workflow_runs()
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


def get_all_persisted_workflow_runs() -> list[AgentWorkflowResponse]:
    return [
        AgentWorkflowResponse.model_validate(_normalize_persisted_workflow_run(run))
        for run in _load_workflow_runs()
    ]


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


def _match_status_then_ticket_workflow(question: str) -> tuple[str, str] | None:
    match = STATUS_AND_TICKET_PATTERN.match(question.strip())
    if not match:
        return None

    return match.group("status").strip(), match.group("ticket").strip()


def _match_status_then_summarize_workflow(question: str) -> tuple[str, str] | None:
    match = STATUS_AND_SUMMARIZE_PATTERN.match(question.strip())
    if not match:
        return None

    return match.group("status").strip(), match.group("summarize").strip()


def _resolve_multistep_workflow(question: str) -> tuple[str | None, str | None, str | None, str | None]:
    planning_mode, llm_plan = generate_llm_workflow_plan(question)

    if llm_plan is not None:
        workflow_kind = llm_plan["workflow_kind"]
        if workflow_kind in {
            "search_then_ticket",
            "search_then_summarize",
            "status_then_ticket",
            "status_then_summarize",
        }:
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

    status_then_ticket = _match_status_then_ticket_workflow(question)
    if status_then_ticket is not None:
        return "status_then_ticket", status_then_ticket[0], status_then_ticket[1], planning_mode

    status_then_summarize = _match_status_then_summarize_workflow(question)
    if status_then_summarize is not None:
        return "status_then_summarize", status_then_summarize[0], status_then_summarize[1], planning_mode

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


def _build_status_context_arguments(tool_output: dict[str, str]) -> dict[str, str]:
    arguments: dict[str, str] = {}

    status = tool_output.get("status", "").strip()
    target = tool_output.get("target", "").strip()
    app_env = tool_output.get("app_env", "").strip()
    requested_environment = tool_output.get("requested_environment", "").strip()

    if status:
        arguments["supporting_status"] = status
    if target:
        arguments["supporting_status_target"] = target
    if app_env:
        arguments["supporting_status_app_env"] = app_env
    if requested_environment:
        arguments["supporting_status_requested_env"] = requested_environment

    if status:
        status_subject = target or "the requested target"
        summary = f"System status snapshot for {status_subject} reported status {status}"
        if app_env:
            summary += f" in {app_env}"
        if requested_environment:
            summary += f" for requested {requested_environment}"
        arguments["supporting_summary"] = f"{summary}."

    return arguments


def _is_ticket_step_with_inherited_context(tool_name: str, action: str) -> bool:
    return tool_name == "ticketing" and action in {"create", "update", "close"}


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


def _build_status_summary(tool_output: dict[str, str]) -> str:
    target = tool_output.get("target", "").strip() or "the requested target"
    status = tool_output.get("status", "").strip() or "unknown"
    app_env = tool_output.get("app_env", "").strip()
    requested_environment = tool_output.get("requested_environment", "").strip()
    chat_provider = tool_output.get("chat_provider", "").strip()
    chat_model = tool_output.get("chat_model", "").strip()

    if requested_environment:
        summary_parts = [f"System status for {target} was requested for {requested_environment} and is {status}"]
    else:
        summary_parts = [f"System status for {target} is {status}"]
    if app_env:
        summary_parts[0] += f" in {app_env}"
    summary_parts[0] += "."

    configuration_bits: list[str] = []
    if chat_provider:
        configuration_bits.append(f"chat provider is {chat_provider}")
    if chat_model:
        configuration_bits.append(f"chat model is {chat_model}")
    if configuration_bits:
        summary_parts.append(f"Current configuration: {', '.join(configuration_bits)}.")

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
    attempt_count: int = 1,
) -> dict:
    return {
        "step_id": f"step_{step_index}",
        "step_index": step_index,
        "step_status": tool_execution.get("execution_status", "completed"),
        "attempt_count": max(1, attempt_count),
        "retried": attempt_count > 1,
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
    attempt_count: int = 1,
) -> dict:
    return {
        "step_id": f"step_{step_index}",
        "step_index": step_index,
        "step_status": "failed",
        "attempt_count": max(1, attempt_count),
        "retried": attempt_count > 1,
        "started_at": started_at,
        "completed_at": completed_at,
        "question": step_question,
        "tool_plan": tool_plan or {},
        "tool_execution": tool_execution,
        "failure_message": failure_message,
    }


def _tool_execution_detail_prefix(step_index: int | None) -> str:
    return f"Step {step_index}: " if step_index is not None else ""


def _normalize_debug_fault_injection(
    debug_fault_injection: dict[str, object] | None,
) -> dict[str, list[dict[str, object]]]:
    normalized_rules: list[dict[str, object]] = []
    raw_rules = (debug_fault_injection or {}).get("tool_execution_failures", [])

    if not isinstance(raw_rules, list):
        return {"tool_execution_failures": normalized_rules}

    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            continue

        tool_name = str(raw_rule.get("tool_name", "")).strip().lower()
        action = str(raw_rule.get("action", "")).strip().lower()
        target = str(raw_rule.get("target", "")).strip()
        message = str(raw_rule.get("message", "")).strip() or "debug injected tool execution failure"
        fail_count = raw_rule.get("fail_count", 0)

        if not tool_name or not action:
            continue
        if not isinstance(fail_count, int) or fail_count <= 0:
            continue

        normalized_rules.append(
            {
                "tool_name": tool_name,
                "action": action,
                "target": target,
                "message": message,
                "remaining_failures": fail_count,
            }
        )

    return {"tool_execution_failures": normalized_rules}


def _consume_injected_tool_execution_failure(
    tool_request: ToolExecutionRequest,
    debug_fault_injection: dict[str, list[dict[str, object]]] | None,
) -> tuple[str | None, int | None]:
    if not debug_fault_injection:
        return None, None

    rules = debug_fault_injection.get("tool_execution_failures", [])
    for rule in rules:
        if rule.get("tool_name") != tool_request.tool_name:
            continue
        if rule.get("action") != tool_request.action:
            continue
        target = str(rule.get("target", "")).strip()
        if target and target != tool_request.target:
            continue

        remaining_failures = rule.get("remaining_failures", 0)
        if not isinstance(remaining_failures, int) or remaining_failures <= 0:
            continue

        rule["remaining_failures"] = remaining_failures - 1
        return str(rule.get("message", "debug injected tool execution failure")), remaining_failures - 1

    return None, None


def _execute_tool_request_with_retry(
    *,
    tool_request: ToolExecutionRequest,
    workflow_trace: list[WorkflowTraceEvent],
    step_index: int | None = None,
    debug_fault_injection: dict[str, list[dict[str, object]]] | None = None,
) -> tuple[dict | None, str | None, str | None, int]:
    attempt_count = 0

    while attempt_count < MAX_TOOL_EXECUTION_RETRIES + 1:
        attempt_count += 1
        try:
            injected_failure_message, remaining_failures = _consume_injected_tool_execution_failure(
                tool_request,
                debug_fault_injection,
            )
            if injected_failure_message:
                prefix = _tool_execution_detail_prefix(step_index)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="fault_injection",
                        status="completed",
                        timestamp=build_utc_timestamp(),
                        detail=(
                            f"{prefix}injected a debug tool execution failure for "
                            f"{tool_request.tool_name}:{tool_request.action}. Remaining injected failures: "
                            f"{remaining_failures}."
                        ),
                    )
                )
                raise RuntimeError(injected_failure_message)
            tool_response = execute_tool_request(tool_request)
            return tool_response.model_dump(), None, None, attempt_count
        except ValueError:
            raise
        except Exception as exc:
            failed_at = build_utc_timestamp()
            failure_message = _format_failure_message(exc)
            prefix = _tool_execution_detail_prefix(step_index)

            if attempt_count <= MAX_TOOL_EXECUTION_RETRIES:
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_execution",
                        status="failed",
                        timestamp=failed_at,
                        detail=(
                            f"{prefix}tool execution attempt {attempt_count} failed for "
                            f"{tool_request.tool_name}:{tool_request.action}: {failure_message}."
                        ),
                    )
                )
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="retry",
                        status="completed",
                        timestamp=build_utc_timestamp(),
                        detail=(
                            f"{prefix}retrying tool execution after attempt {attempt_count} "
                            f"failed."
                        ),
                    )
                )
                continue

            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_execution",
                    status="failed",
                    timestamp=failed_at,
                    detail=(
                        f"{prefix}tool execution failed for {tool_request.tool_name}:{tool_request.action} "
                        f"after {attempt_count} attempt(s): {failure_message}."
                    ),
                )
            )
            return None, failed_at, failure_message, attempt_count

    return None, None, "unreachable_retry_state", attempt_count


def _normalize_confirmation(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "confirmed", "continue"}


def _extract_resume_ticket_overrides(clarification_context: dict[str, str]) -> dict[str, str]:
    overrides: dict[str, str] = {}

    for key in ("environment", "severity", "status", "ticket_id"):
        value = clarification_context.get(key, "").strip()
        if value:
            overrides[key] = value

    return overrides


def _can_resume_from_failed_step(source_run: AgentWorkflowResponse) -> bool:
    return _is_failed_step_resume_eligible(source_run)


def _copy_workflow_step_record(step) -> dict:
    return step.model_dump() if hasattr(step, "model_dump") else dict(step)


def _resume_failed_step_run(
    *,
    source_run: AgentWorkflowResponse,
    clarification_context: dict[str, str],
    top_k: int,
    debug_fault_injection: dict[str, object] | None = None,
) -> AgentWorkflowResponse:
    del top_k
    workflow_started_at = build_utc_timestamp()
    tool_planning_latency_ms = 0
    debug_fault_injection_state = _normalize_debug_fault_injection(debug_fault_injection)
    workflow_kind, workflow_search_question, workflow_follow_up_question, _ = _resolve_multistep_workflow(
        source_run.question
    )
    if workflow_kind not in {"search_then_ticket", "status_then_ticket"}:
        raise ValueError("failed_step_resume_not_supported")
    if not workflow_search_question or not workflow_follow_up_question:
        raise ValueError("failed_step_resume_not_supported")

    reusable_step = source_run.tool_chain[0]
    failed_step = source_run.tool_chain[-1]
    reusable_output = (
        reusable_step.tool_execution.get("output", {})
        if isinstance(reusable_step.tool_execution, dict)
        else {}
    )
    if workflow_kind == "search_then_ticket":
        inherited_context = _build_search_context_arguments(reusable_output)
        reuse_detail = (
            "Reused completed search step from the source workflow run and continued from "
            "the failed ticket step."
        )
    else:
        inherited_context = _build_status_context_arguments(reusable_output)
        reuse_detail = (
            "Reused completed system status step from the source workflow run and continued "
            "from the failed ticket step."
        )

    workflow_trace = [
        WorkflowTraceEvent(
            stage="resume_reuse",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=reuse_detail,
        )
    ]
    ticket_resume_overrides = _extract_resume_ticket_overrides(clarification_context)
    step_started_at = build_utc_timestamp()
    tool_planner_started_at = time.perf_counter()
    try:
        tool_plan = plan_tool_request(workflow_follow_up_question)
    except ValueError:
        tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
        raise
    except Exception as exc:
        tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
        failed_at = build_utc_timestamp()
        failure_message = _format_failure_message(exc)
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_planning",
                status="failed",
                timestamp=failed_at,
                detail=f"Step 2: tool planning failed during failed-step resume: {failure_message}.",
            )
        )
        response = _build_failed_workflow_response(
            question=source_run.question,
            route=source_run.route,
            workflow_trace=workflow_trace,
            filename=source_run.filename,
            started_at=workflow_started_at,
            failed_at=failed_at,
            terminal_reason="tool_planning_failed",
            failure_stage="tool_planning",
            failure_message=failure_message,
            step_count=2,
            tool_chain=[
                _build_failed_workflow_step_record(
                    step_index=2,
                    step_question=failed_step.question,
                    started_at=step_started_at,
                    completed_at=failed_at,
                    failure_message=failure_message,
                )
            ],
            tool_planning_latency_ms=tool_planning_latency_ms,
        )
        response.resumed_from_step_index = 2
        response.reused_step_indices = [1]
        return response
    tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
    if inherited_context:
        tool_plan.arguments = {
            **inherited_context,
            **tool_plan.arguments,
        }
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_context",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail="Step 2 reused supporting context from the completed step 1 output.",
            )
        )
    if ticket_resume_overrides:
        tool_plan.arguments = {
            **tool_plan.arguments,
            **ticket_resume_overrides,
        }
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="resume_context",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail="Applied structured clarification fields while resuming the failed ticket step.",
            )
        )
    workflow_trace.append(
        WorkflowTraceEvent(
            stage="tool_planning",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=(
                f"Step 2: replanned {tool_plan.tool_name}:{tool_plan.action} for "
                f"{tool_plan.target} during failed-step resume."
            ),
        )
    )
    tool_response, failed_at, failure_message, attempt_count = _execute_tool_request_with_retry(
        tool_request=ToolExecutionRequest(
            tool_name=tool_plan.tool_name,
            action=tool_plan.action,
            target=tool_plan.target,
            arguments=tool_plan.arguments,
        ),
        workflow_trace=workflow_trace,
        step_index=2,
        debug_fault_injection=debug_fault_injection_state,
    )
    if tool_response is None:
        response = _build_failed_workflow_response(
            question=source_run.question,
            route=source_run.route,
            workflow_trace=workflow_trace,
            filename=source_run.filename,
            started_at=workflow_started_at,
            failed_at=failed_at,
            terminal_reason="tool_execution_failed",
            failure_stage="tool_execution",
            failure_message=failure_message,
            step_count=2,
            tool_plan=tool_plan.model_dump(),
            tool_chain=[
                _build_failed_workflow_step_record(
                    step_index=2,
                    step_question=failed_step.question,
                    started_at=step_started_at,
                    completed_at=failed_at,
                    failure_message=failure_message,
                    tool_plan=tool_plan.model_dump(),
                    attempt_count=attempt_count,
                )
            ],
            tool_planning_latency_ms=tool_planning_latency_ms,
        )
        response.resumed_from_step_index = 2
        response.reused_step_indices = [1]
        return response

    step_completed_at = build_utc_timestamp()
    workflow_trace.append(
        WorkflowTraceEvent(
            stage="tool_execution",
            status="completed",
            timestamp=step_completed_at,
            detail=(
                f"Step 2: executed {tool_response['execution_mode']} tool "
                f"{tool_response['tool_name']}:{tool_response['action']} with status "
                f"{tool_response['execution_status']}"
                + (f" after {attempt_count} attempt(s)." if attempt_count > 1 else ".")
            ),
        )
    )
    response = AgentWorkflowResponse(
        question=source_run.question,
        workflow_status="completed",
        step_count=2,
        route=source_run.route,
        workflow_trace=workflow_trace,
        filename=source_run.filename,
        tool_plan=tool_plan.model_dump(),
        tool_execution=tool_response,
        tool_chain=[
            _build_workflow_step_record(
                step_index=2,
                step_question=failed_step.question,
                tool_plan=tool_plan.model_dump(),
                tool_execution=tool_response,
                started_at=step_started_at,
                completed_at=step_completed_at,
                attempt_count=attempt_count,
            )
        ],
        resumed_from_step_index=2,
        reused_step_indices=[1],
        tool_planning_latency_ms=tool_planning_latency_ms,
    )
    return _finalize_workflow_response(
        response,
        started_at=workflow_started_at,
        terminal_reason="tool_execution_completed",
        completed_at=step_completed_at,
    )


def _resume_failed_summary_run(
    *,
    source_run: AgentWorkflowResponse,
) -> AgentWorkflowResponse:
    workflow_started_at = build_utc_timestamp()
    workflow_kind, _, workflow_follow_up_question, _ = _resolve_multistep_workflow(source_run.question)
    if workflow_kind not in {"search_then_summarize", "status_then_summarize"}:
        raise ValueError("failed_step_resume_not_supported")
    if not workflow_follow_up_question:
        raise ValueError("failed_step_resume_not_supported")

    reusable_step = source_run.tool_chain[0]
    reusable_step_dump = _copy_workflow_step_record(reusable_step)
    reusable_tool_execution = reusable_step_dump.get("tool_execution")
    reusable_output = (
        reusable_tool_execution.get("output", {})
        if isinstance(reusable_tool_execution, dict)
        else {}
    )

    if workflow_kind == "search_then_summarize":
        reuse_detail = (
            "Reused completed search step from the source workflow run and continued "
            "with local summary generation."
        )
        summary_stage = "search_summary"
        summary_terminal_reason = "search_summary_completed"
        failure_terminal_reason = "search_summary_failed"
        failure_stage = "search_summary"
        summary_builder = _build_search_summary
        answer_source = "local_search_summary"
    else:
        reuse_detail = (
            "Reused completed system status step from the source workflow run and continued "
            "with local summary generation."
        )
        summary_stage = "status_summary"
        summary_terminal_reason = "status_summary_completed"
        failure_terminal_reason = "status_summary_failed"
        failure_stage = "status_summary"
        summary_builder = _build_status_summary
        answer_source = "local_status_summary"

    workflow_trace = [
        WorkflowTraceEvent(
            stage="resume_reuse",
            status="completed",
            timestamp=build_utc_timestamp(),
            detail=reuse_detail,
        )
    ]

    try:
        summary_answer = summary_builder(reusable_output)
    except Exception as exc:
        failed_at = build_utc_timestamp()
        failure_message = _format_failure_message(exc)
        workflow_trace.append(
            WorkflowTraceEvent(
                stage=summary_stage,
                status="failed",
                timestamp=failed_at,
                detail=f"{summary_stage.replace('_', ' ').title()} failed during failed-step resume: {failure_message}.",
            )
        )
        response = _build_failed_workflow_response(
            question=source_run.question,
            route=source_run.route,
            workflow_trace=workflow_trace,
            filename=source_run.filename,
            started_at=workflow_started_at,
            failed_at=failed_at,
            terminal_reason=failure_terminal_reason,
            failure_stage=failure_stage,
            failure_message=failure_message,
            step_count=2,
            tool_plan=source_run.tool_plan,
            tool_execution=source_run.tool_execution,
            tool_chain=[reusable_step_dump],
        )
        response.resumed_from_step_index = 2
        response.reused_step_indices = [1]
        return response

    answered_at = build_utc_timestamp()
    workflow_trace.append(
        WorkflowTraceEvent(
            stage=summary_stage,
            status="completed",
            timestamp=answered_at,
            detail=f"Generated a local summary from the reused step 1 output for '{workflow_follow_up_question}'.",
        )
    )
    response = AgentWorkflowResponse(
        question=source_run.question,
        workflow_status="completed",
        step_count=2,
        route=source_run.route,
        workflow_trace=workflow_trace,
        filename=source_run.filename,
        answer=summary_answer,
        answer_source=answer_source,
        model="local-heuristic-summary",
        answered_at=answered_at,
        answer_latency_ms=0.0,
        chat_provider="local",
        chat_model="local-heuristic-summary",
        tool_plan=source_run.tool_plan,
        tool_execution=source_run.tool_execution,
        tool_chain=[reusable_step_dump],
        resumed_from_step_index=2,
        reused_step_indices=[1],
    )
    return _finalize_workflow_response(
        response,
        started_at=workflow_started_at,
        terminal_reason=summary_terminal_reason,
        completed_at=answered_at,
    )


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


def _resume_status_question(
    status_question: str,
    clarification_context: dict[str, str],
) -> str:
    del clarification_context
    return status_question.strip()


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
    debug_fault_injection: dict[str, object] | None = None,
    recovered_via_action: str | None = None,
) -> AgentWorkflowResponse:
    source_run: AgentWorkflowResponse | None = None
    if run_id and run_id.strip():
        source_run = get_persisted_workflow_run(run_id.strip())
        source_question = source_run.question
        source_filename = source_run.filename
        source_run_id = source_run.run_id
        resume_source_type = "run_id"
    else:
        if not clarification_context:
            raise ValueError("clarification_context_required")
        source_question, source_filename, source_run_id, resume_source_type = _resolve_resume_source(
            original_question, run_id
        )

    if (
        source_run is not None
        and _can_resume_from_failed_step(source_run)
    ):
        applied_clarification_fields = _extract_applied_clarification_fields(clarification_context)
        overridden_plan_arguments = _extract_overridden_plan_arguments(clarification_context)
        workflow_kind = _resolve_multistep_workflow(source_run.question)[0]
        resume_strategy = f"{workflow_kind}_failed_step_resume"
        if workflow_kind in {"search_then_ticket", "status_then_ticket"}:
            response = _resume_failed_step_run(
                source_run=source_run,
                clarification_context=clarification_context,
                top_k=top_k,
                debug_fault_injection=debug_fault_injection,
            )
        else:
            response = _resume_failed_summary_run(
                source_run=source_run,
            )
        response.workflow_trace.insert(
            0,
            WorkflowTraceEvent(
                stage="workflow_resume",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail=(
                    f"Resumed workflow from failed step 2 of '{source_question}' via {resume_source_type} "
                    f"using {resume_strategy} with fields: "
                    f"{', '.join(applied_clarification_fields) if applied_clarification_fields else 'none'}; "
                    f"overridden arguments: "
                    f"{', '.join(overridden_plan_arguments) if overridden_plan_arguments else 'none'}."
                ),
            ),
        )
        response.resume_source_type = resume_source_type
        response.recovered_via_action = recovered_via_action
        response.resume_strategy = resume_strategy
        response.applied_clarification_fields = applied_clarification_fields
        response.question_rewritten = False
        response.overridden_plan_arguments = overridden_plan_arguments
        return _persist_workflow_response(
            response=response,
            resumed_from_question=source_question,
            source_run_id=source_run_id,
        )

    if source_run is not None and not clarification_context:
        if source_run.workflow_status == "completed":
            raise ValueError("source_run_not_failed_step_resumable")
        raise ValueError("source_run_not_eligible_for_failed_step_resume")

    if not clarification_context:
        raise ValueError("clarification_context_required")

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

    elif workflow_kind == "status_then_ticket" and workflow_search_question and workflow_follow_up_question:
        resume_strategy = "status_then_ticket_resume"
        status_question, ticket_question = workflow_search_question, workflow_follow_up_question
        resumed_status = _resume_status_question(status_question, clarification_context)
        resumed_ticket = _resume_ticket_question(ticket_question, clarification_context)
        resumed_question = f"{resumed_status} and {resumed_ticket}"

    elif (
        workflow_kind == "status_then_summarize"
        and workflow_search_question
        and workflow_follow_up_question
    ):
        resume_strategy = "status_then_summarize_resume"
        status_question, summarize_question = workflow_search_question, workflow_follow_up_question
        resumed_status = _resume_status_question(status_question, clarification_context)
        resumed_question = f"{resumed_status} and {summarize_question}"

    else:
        resumed_question = _resume_generic_question(original_question, clarification_context)

    response = orchestrate_agent_request(
        question=resumed_question,
        filename=filename if filename is not None else source_filename,
        top_k=top_k,
        resume_context=clarification_context,
        persist_run=False,
        debug_fault_injection=debug_fault_injection,
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
    response.recovered_via_action = recovered_via_action
    response.resume_strategy = resume_strategy
    response.applied_clarification_fields = applied_clarification_fields
    response.question_rewritten = resumed_question != source_question
    response.overridden_plan_arguments = overridden_plan_arguments
    return _persist_workflow_response(
        response=response,
        resumed_from_question=source_question,
        source_run_id=source_run_id,
    )


def recover_agent_request(
    *,
    run_id: str,
    recovery_action: str | None = None,
    clarification_context: dict[str, str] | None = None,
    filename: str | None = None,
    top_k: int = 3,
    debug_fault_injection: dict[str, object] | None = None,
) -> AgentWorkflowResponse:
    source_run = get_persisted_workflow_run(run_id)
    available_actions = source_run.available_recovery_actions or _derive_available_recovery_actions(source_run)
    selected_action = recovery_action.strip() if isinstance(recovery_action, str) and recovery_action.strip() else (
        source_run.recommended_recovery_action or _derive_recommended_recovery_action(source_run)
    )
    clarification_context = clarification_context or {}

    if not selected_action or selected_action == "none":
        raise ValueError("no_recovery_action_available")
    if selected_action not in available_actions:
        raise ValueError("recovery_action_not_available")

    if selected_action in {"resume_from_failed_step", "resume_with_clarification"}:
        return resume_agent_request(
            original_question=source_run.question,
            clarification_context=clarification_context,
            run_id=source_run.run_id,
            filename=filename if filename is not None else source_run.filename,
            top_k=top_k,
            debug_fault_injection=debug_fault_injection,
            recovered_via_action=selected_action,
        )

    if selected_action in {"manual_retrigger", "retry"}:
        response = orchestrate_agent_request(
            question=source_run.question,
            filename=filename if filename is not None else source_run.filename,
            top_k=top_k,
            persist_run=False,
            debug_fault_injection=debug_fault_injection,
        )
        response.workflow_trace.insert(
            0,
            WorkflowTraceEvent(
                stage="workflow_recovery",
                status="completed",
                timestamp=build_utc_timestamp(),
                detail=(
                    f"Recovered workflow from run_id via {selected_action} using "
                    f"{'retry_recovery' if selected_action == 'retry' else 'manual_retrigger_recovery'}."
                ),
            ),
        )
        response.resume_source_type = "run_id"
        response.recovered_via_action = selected_action
        response.resume_strategy = (
            "retry_recovery" if selected_action == "retry" else "manual_retrigger_recovery"
        )
        response.applied_clarification_fields = []
        response.question_rewritten = False
        response.overridden_plan_arguments = []
        return _persist_workflow_response(
            response=response,
            resumed_from_question=source_run.question,
            source_run_id=source_run.run_id,
        )

    if selected_action == "manual_investigation":
        raise ValueError("manual_investigation_not_executable")

    raise ValueError("unsupported_recovery_action")


def orchestrate_agent_request(
    question: str,
    filename: str | None = None,
    top_k: int = 3,
    resume_context: dict[str, str] | None = None,
    persist_run: bool = True,
    debug_fault_injection: dict[str, object] | None = None,
) -> AgentWorkflowResponse:
    """Route and execute the next workflow step for an agent request."""
    workflow_started_at = build_utc_timestamp()
    workflow_planning_latency_ms = 0
    tool_planning_latency_ms = 0
    clarification_planning_latency_ms = 0
    debug_fault_injection_state = _normalize_debug_fault_injection(debug_fault_injection)
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
        workflow_planner_started_at = time.perf_counter()
        workflow_kind, workflow_search_question, workflow_follow_up_question, workflow_planning_mode = (
            _resolve_multistep_workflow(question)
        )
        workflow_planning_latency_ms += _elapsed_ms(workflow_planner_started_at)
        resume_context = resume_context or {}

        if workflow_kind in {
            "search_then_ticket",
            "search_then_summarize",
            "status_then_ticket",
            "status_then_summarize",
        }:
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
                tool_planner_started_at = time.perf_counter()
                try:
                    tool_plan = plan_tool_request(step_question)
                except ValueError:
                    tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
                    raise
                except Exception as exc:
                    tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
                        workflow_planning_latency_ms=workflow_planning_latency_ms,
                        tool_planning_latency_ms=tool_planning_latency_ms,
                        clarification_planning_latency_ms=clarification_planning_latency_ms,
                    )
                    return _persist_workflow_response(response) if persist_run else response
                tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
                if (
                    step_index == 2
                    and _is_ticket_step_with_inherited_context(tool_plan.tool_name, tool_plan.action)
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
                                "before the ticket step."
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
                tool_response, failed_at, failure_message, attempt_count = _execute_tool_request_with_retry(
                    tool_request=ToolExecutionRequest(
                        tool_name=tool_plan.tool_name,
                        action=tool_plan.action,
                        target=tool_plan.target,
                        arguments=tool_plan.arguments,
                    ),
                    workflow_trace=workflow_trace,
                    step_index=step_index,
                    debug_fault_injection=debug_fault_injection_state,
                )
                if tool_response is None:
                    chained_steps.append(
                        _build_failed_workflow_step_record(
                            step_index=step_index,
                            step_question=step_question,
                            started_at=step_started_at,
                            completed_at=failed_at,
                            failure_message=failure_message,
                            tool_plan=tool_plan.model_dump(),
                            attempt_count=attempt_count,
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
                        workflow_planning_latency_ms=workflow_planning_latency_ms,
                        tool_planning_latency_ms=tool_planning_latency_ms,
                        clarification_planning_latency_ms=clarification_planning_latency_ms,
                    )
                    return _persist_workflow_response(response) if persist_run else response
                step_completed_at = build_utc_timestamp()
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_execution",
                        status="completed",
                        timestamp=step_completed_at,
                        detail=(
                            f"Step {step_index}: executed {tool_response['execution_mode']} tool "
                            f"{tool_response['tool_name']}:{tool_response['action']} "
                            f"with status {tool_response['execution_status']}"
                            + (f" after {attempt_count} attempt(s)." if attempt_count > 1 else ".")
                        ),
                    )
                )
                chained_steps.append(
                    _build_workflow_step_record(
                        step_index=step_index,
                        step_question=step_question,
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response,
                        started_at=step_started_at,
                        completed_at=step_completed_at,
                        attempt_count=attempt_count,
                    )
                )

                if (
                    step_index == 1
                    and tool_response["tool_name"] == "document_search"
                    and tool_response["output"].get("matched_count") == "0"
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
                    clarification_planner_started_at = time.perf_counter()
                    clarification_plan = plan_search_miss_clarification(
                        search_query=tool_plan.target,
                        next_action_question=ticket_question,
                    )
                    clarification_planning_latency_ms += _elapsed_ms(clarification_planner_started_at)
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="clarification_planning",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail=(
                                "Search produced no supporting documents, so the workflow "
                                "stopped before the ticket step and requested clarification."
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
                            "needs clarification before continuing to the ticket step."
                        ),
                        clarification_plan=clarification_plan.model_dump(),
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response,
                        step_count=len(chained_steps),
                        tool_chain=chained_steps,
                        workflow_planning_latency_ms=workflow_planning_latency_ms,
                        tool_planning_latency_ms=tool_planning_latency_ms,
                        clarification_planning_latency_ms=clarification_planning_latency_ms,
                    )
                    response = _finalize_workflow_response(
                        response,
                        started_at=workflow_started_at,
                        terminal_reason="search_miss_clarification",
                        last_updated_at=workflow_trace[-1].timestamp,
                    )
                    return _persist_workflow_response(response) if persist_run else response

                if step_index == 1 and tool_response["tool_name"] == "document_search":
                    prior_search_context = _build_search_context_arguments(tool_response["output"])

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
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="tool_execution_completed",
                completed_at=workflow_trace[-1].timestamp,
            )
            return _persist_workflow_response(response) if persist_run else response

        if workflow_kind == "status_then_ticket" and workflow_search_question and workflow_follow_up_question:
            status_question, ticket_question = workflow_search_question, workflow_follow_up_question
            prior_status_context: dict[str, str] = {}

            for step_index, step_question in enumerate((status_question, ticket_question), start=1):
                step_started_at = build_utc_timestamp()
                tool_planner_started_at = time.perf_counter()
                try:
                    tool_plan = plan_tool_request(step_question)
                except ValueError:
                    tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
                    raise
                except Exception as exc:
                    tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
                        workflow_planning_latency_ms=workflow_planning_latency_ms,
                        tool_planning_latency_ms=tool_planning_latency_ms,
                        clarification_planning_latency_ms=clarification_planning_latency_ms,
                    )
                    return _persist_workflow_response(response) if persist_run else response
                tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
                if (
                    step_index == 2
                    and _is_ticket_step_with_inherited_context(tool_plan.tool_name, tool_plan.action)
                    and prior_status_context
                ):
                    tool_plan.arguments = {
                        **prior_status_context,
                        **tool_plan.arguments,
                    }
                    workflow_trace.append(
                        WorkflowTraceEvent(
                            stage="tool_context",
                            status="completed",
                            timestamp=build_utc_timestamp(),
                            detail=(
                                "Step 2 inherited supporting system status context from step 1 "
                                "before the ticket step."
                            ),
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
                tool_response, failed_at, failure_message, attempt_count = _execute_tool_request_with_retry(
                    tool_request=ToolExecutionRequest(
                        tool_name=tool_plan.tool_name,
                        action=tool_plan.action,
                        target=tool_plan.target,
                        arguments=tool_plan.arguments,
                    ),
                    workflow_trace=workflow_trace,
                    step_index=step_index,
                    debug_fault_injection=debug_fault_injection_state,
                )
                if tool_response is None:
                    chained_steps.append(
                        _build_failed_workflow_step_record(
                            step_index=step_index,
                            step_question=step_question,
                            started_at=step_started_at,
                            completed_at=failed_at,
                            failure_message=failure_message,
                            tool_plan=tool_plan.model_dump(),
                            attempt_count=attempt_count,
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
                        workflow_planning_latency_ms=workflow_planning_latency_ms,
                        tool_planning_latency_ms=tool_planning_latency_ms,
                        clarification_planning_latency_ms=clarification_planning_latency_ms,
                    )
                    return _persist_workflow_response(response) if persist_run else response
                step_completed_at = build_utc_timestamp()
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="tool_execution",
                        status="completed",
                        timestamp=step_completed_at,
                        detail=(
                            f"Step {step_index}: executed {tool_response['execution_mode']} tool "
                            f"{tool_response['tool_name']}:{tool_response['action']} "
                            f"with status {tool_response['execution_status']}"
                            + (f" after {attempt_count} attempt(s)." if attempt_count > 1 else ".")
                        ),
                    )
                )
                chained_steps.append(
                    _build_workflow_step_record(
                        step_index=step_index,
                        step_question=step_question,
                        tool_plan=tool_plan.model_dump(),
                        tool_execution=tool_response,
                        started_at=step_started_at,
                        completed_at=step_completed_at,
                        attempt_count=attempt_count,
                    )
                )

                if step_index == 1 and tool_response["tool_name"] == "system_status":
                    prior_status_context = _build_status_context_arguments(tool_response["output"])

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
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
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
            tool_planner_started_at = time.perf_counter()
            try:
                tool_plan = plan_tool_request(search_question)
            except ValueError:
                tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
                raise
            except Exception as exc:
                tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
                )
                return _persist_workflow_response(response) if persist_run else response
            tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
            tool_response, failed_at, failure_message, attempt_count = _execute_tool_request_with_retry(
                tool_request=ToolExecutionRequest(
                    tool_name=tool_plan.tool_name,
                    action=tool_plan.action,
                    target=tool_plan.target,
                    arguments=tool_plan.arguments,
                ),
                workflow_trace=workflow_trace,
                step_index=1,
                debug_fault_injection=debug_fault_injection_state,
            )
            if tool_response is None:
                chained_steps.append(
                    _build_failed_workflow_step_record(
                        step_index=1,
                        step_question=search_question,
                        started_at=step_started_at,
                        completed_at=failed_at,
                        failure_message=failure_message,
                        tool_plan=tool_plan.model_dump(),
                        attempt_count=attempt_count,
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
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
                )
                return _persist_workflow_response(response) if persist_run else response
            step_completed_at = build_utc_timestamp()
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_execution",
                    status="completed",
                    timestamp=step_completed_at,
                    detail=(
                        f"Executed {tool_response['execution_mode']} tool "
                        f"{tool_response['tool_name']}:{tool_response['action']} "
                        f"with status {tool_response['execution_status']}"
                        + (f" after {attempt_count} attempt(s)." if attempt_count > 1 else ".")
                    ),
                )
            )
            chained_steps.append(
                _build_workflow_step_record(
                    step_index=1,
                    step_question=search_question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response,
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                    attempt_count=attempt_count,
                )
            )

            if tool_response["output"].get("matched_count") == "0":
                clarification_planner_started_at = time.perf_counter()
                clarification_plan = plan_search_summary_miss_clarification(tool_plan.target)
                clarification_planning_latency_ms += _elapsed_ms(clarification_planner_started_at)
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
                    tool_execution=tool_response,
                    step_count=len(chained_steps),
                    tool_chain=chained_steps,
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
                )
                response = _finalize_workflow_response(
                    response,
                    started_at=workflow_started_at,
                    terminal_reason="search_summary_miss_clarification",
                    last_updated_at=workflow_trace[-1].timestamp,
                )
                return _persist_workflow_response(response) if persist_run else response

            try:
                summary_answer = _build_search_summary(tool_response["output"])
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
                    tool_execution=tool_response,
                    tool_chain=chained_steps,
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
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
                tool_execution=tool_response,
                step_count=len(chained_steps),
                tool_chain=chained_steps,
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="search_summary_completed",
                completed_at=answered_at,
            )
            return _persist_workflow_response(response) if persist_run else response

        if workflow_kind == "status_then_summarize" and workflow_search_question and workflow_follow_up_question:
            status_question, summarize_question = workflow_search_question, workflow_follow_up_question
            step_started_at = build_utc_timestamp()
            tool_planner_started_at = time.perf_counter()
            try:
                tool_plan = plan_tool_request(status_question)
            except ValueError:
                tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
                raise
            except Exception as exc:
                tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
                        step_question=status_question,
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
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
                )
                return _persist_workflow_response(response) if persist_run else response
            tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
            tool_response, failed_at, failure_message, attempt_count = _execute_tool_request_with_retry(
                tool_request=ToolExecutionRequest(
                    tool_name=tool_plan.tool_name,
                    action=tool_plan.action,
                    target=tool_plan.target,
                    arguments=tool_plan.arguments,
                ),
                workflow_trace=workflow_trace,
                step_index=1,
                debug_fault_injection=debug_fault_injection_state,
            )
            if tool_response is None:
                chained_steps.append(
                    _build_failed_workflow_step_record(
                        step_index=1,
                        step_question=status_question,
                        started_at=step_started_at,
                        completed_at=failed_at,
                        failure_message=failure_message,
                        tool_plan=tool_plan.model_dump(),
                        attempt_count=attempt_count,
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
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
                )
                return _persist_workflow_response(response) if persist_run else response
            step_completed_at = build_utc_timestamp()
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="tool_execution",
                    status="completed",
                    timestamp=step_completed_at,
                    detail=(
                        f"Executed {tool_response['execution_mode']} tool "
                        f"{tool_response['tool_name']}:{tool_response['action']} "
                        f"with status {tool_response['execution_status']}"
                        + (f" after {attempt_count} attempt(s)." if attempt_count > 1 else ".")
                    ),
                )
            )
            chained_steps.append(
                _build_workflow_step_record(
                    step_index=1,
                    step_question=status_question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response,
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                    attempt_count=attempt_count,
                )
            )

            try:
                summary_answer = _build_status_summary(tool_response["output"])
            except Exception as exc:
                failed_at = build_utc_timestamp()
                failure_message = _format_failure_message(exc)
                workflow_trace.append(
                    WorkflowTraceEvent(
                        stage="status_summary",
                        status="failed",
                        timestamp=failed_at,
                        detail=f"Status summary generation failed: {failure_message}.",
                    )
                )
                response = _build_failed_workflow_response(
                    question=question,
                    route=route,
                    workflow_trace=workflow_trace,
                    filename=filename,
                    started_at=workflow_started_at,
                    failed_at=failed_at,
                    terminal_reason="status_summary_failed",
                    failure_stage="status_summary",
                    failure_message=failure_message,
                    step_count=len(chained_steps),
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response,
                    tool_chain=chained_steps,
                    workflow_planning_latency_ms=workflow_planning_latency_ms,
                    tool_planning_latency_ms=tool_planning_latency_ms,
                    clarification_planning_latency_ms=clarification_planning_latency_ms,
                )
                return _persist_workflow_response(response) if persist_run else response
            workflow_trace.append(
                WorkflowTraceEvent(
                    stage="status_summary",
                    status="completed",
                    timestamp=build_utc_timestamp(),
                    detail=(
                        f"Generated a local summary for system status results in response to "
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
                answer_source="local_status_summary",
                model="local-heuristic-summary",
                answered_at=answered_at,
                answer_latency_ms=0.0,
                chat_provider="local",
                chat_model="local-heuristic-summary",
                tool_plan=tool_plan.model_dump(),
                tool_execution=tool_response,
                step_count=len(chained_steps),
                tool_chain=chained_steps,
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="status_summary_completed",
                completed_at=answered_at,
            )
            return _persist_workflow_response(response) if persist_run else response

        step_started_at = build_utc_timestamp()
        tool_planner_started_at = time.perf_counter()
        try:
            tool_plan = plan_tool_request(question)
        except ValueError:
            tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
            raise
        except Exception as exc:
            tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
            )
            return _persist_workflow_response(response) if persist_run else response
        tool_planning_latency_ms += _elapsed_ms(tool_planner_started_at)
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
            clarification_planner_started_at = time.perf_counter()
            clarification_plan = plan_unsupported_action_clarification(question, tool_plan.target)
            clarification_planning_latency_ms += _elapsed_ms(clarification_planner_started_at)
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
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
            )
            response = _finalize_workflow_response(
                response,
                started_at=workflow_started_at,
                terminal_reason="unsupported_action_clarification",
                last_updated_at=clarification_timestamp,
            )
            return _persist_workflow_response(response) if persist_run else response
        tool_response, failed_at, failure_message, attempt_count = _execute_tool_request_with_retry(
            tool_request=ToolExecutionRequest(
                tool_name=tool_plan.tool_name,
                action=tool_plan.action,
                target=tool_plan.target,
                arguments=tool_plan.arguments,
            ),
            workflow_trace=workflow_trace,
            step_index=1,
            debug_fault_injection=debug_fault_injection_state,
        )
        if tool_response is None:
            failed_step = _build_failed_workflow_step_record(
                step_index=1,
                step_question=question,
                started_at=step_started_at,
                completed_at=failed_at,
                failure_message=failure_message,
                tool_plan=tool_plan.model_dump(),
                attempt_count=attempt_count,
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
                workflow_planning_latency_ms=workflow_planning_latency_ms,
                tool_planning_latency_ms=tool_planning_latency_ms,
                clarification_planning_latency_ms=clarification_planning_latency_ms,
            )
            return _persist_workflow_response(response) if persist_run else response
        step_completed_at = build_utc_timestamp()
        workflow_trace.append(
            WorkflowTraceEvent(
                stage="tool_execution",
                status="completed",
                timestamp=step_completed_at,
                detail=(
                    f"Executed {tool_response['execution_mode']} tool "
                    f"{tool_response['tool_name']}:{tool_response['action']} "
                    f"with status {tool_response['execution_status']}"
                    + (f" after {attempt_count} attempt(s)." if attempt_count > 1 else ".")
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
            tool_execution=tool_response,
            tool_chain=[
                _build_workflow_step_record(
                    step_index=1,
                    step_question=question,
                    tool_plan=tool_plan.model_dump(),
                    tool_execution=tool_response,
                    started_at=step_started_at,
                    completed_at=step_completed_at,
                    attempt_count=attempt_count,
                )
            ],
            workflow_planning_latency_ms=workflow_planning_latency_ms,
            tool_planning_latency_ms=tool_planning_latency_ms,
            clarification_planning_latency_ms=clarification_planning_latency_ms,
        )
        response = _finalize_workflow_response(
            response,
            started_at=workflow_started_at,
            terminal_reason="tool_execution_completed",
            completed_at=step_completed_at,
        )
        return _persist_workflow_response(response) if persist_run else response

    clarification_planner_started_at = time.perf_counter()
    clarification_plan = plan_clarification(question)
    clarification_planning_latency_ms += _elapsed_ms(clarification_planner_started_at)
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
        workflow_planning_latency_ms=workflow_planning_latency_ms,
        tool_planning_latency_ms=tool_planning_latency_ms,
        clarification_planning_latency_ms=clarification_planning_latency_ms,
    )
    response = _finalize_workflow_response(
        response,
        started_at=workflow_started_at,
        terminal_reason="clarification_requested",
        last_updated_at=workflow_trace[-1].timestamp,
    )
    return _persist_workflow_response(response) if persist_run else response
