from app.core.config import DATA_ROOT
from app.schemas.query import AgentWorkflowResponse, AgentWorkflowRunListResponse, AgentWorkflowRunSummary
from app.services.agent.state_store import JsonListRepository


WORKFLOW_RUN_DATA_DIR = DATA_ROOT / "tool_state"
WORKFLOW_RUN_DATA_DIR.mkdir(parents=True, exist_ok=True)
AGENT_V2_RUN_STORE_PATH = WORKFLOW_RUN_DATA_DIR / "workflow_runs_v2.json"


def _load_runs() -> list[dict]:
    return JsonListRepository(AGENT_V2_RUN_STORE_PATH).load()


def _save_runs(runs: list[dict]) -> None:
    JsonListRepository(AGENT_V2_RUN_STORE_PATH).save(runs)


def persist_agent_v2_run(response: AgentWorkflowResponse) -> None:
    runs = _load_runs()
    payload = response.model_dump(mode="json")
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return

    updated = False
    normalized_run_id = run_id.strip()
    for index, existing in enumerate(runs):
        if existing.get("run_id") == normalized_run_id:
            runs[index] = payload
            updated = True
            break

    if not updated:
        runs.append(payload)

    runs.sort(key=lambda item: item.get("last_updated_at") or "", reverse=True)
    _save_runs(runs)


def get_persisted_agent_v2_run(run_id: str) -> AgentWorkflowResponse:
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        raise ValueError("run_id_must_not_be_empty")

    for run in _load_runs():
        if run.get("run_id") == normalized_run_id:
            return AgentWorkflowResponse.model_validate(run)

    raise FileNotFoundError("agent_v2_run_not_found")


def get_all_persisted_agent_v2_runs() -> list[AgentWorkflowResponse]:
    return [
        AgentWorkflowResponse.model_validate(run)
        for run in _load_runs()
        if isinstance(run, dict) and run.get("run_id")
    ]


def list_persisted_agent_v2_runs(limit: int = 20) -> AgentWorkflowRunListResponse:
    if limit <= 0:
        raise ValueError("limit_must_be_positive")

    runs = _load_runs()[:limit]
    summaries = [
        AgentWorkflowRunSummary(
            run_id=run["run_id"],
            root_run_id=run.get("root_run_id"),
            recovery_depth=run.get("recovery_depth", 0),
            question=run.get("question", ""),
            resumed_from_question=run.get("resumed_from_question"),
            source_run_id=run.get("source_run_id"),
            recovered_via_action=run.get("recovered_via_action"),
            resume_source_type=run.get("resume_source_type"),
            resume_strategy=run.get("resume_strategy"),
            resumed_from_step_index=run.get("resumed_from_step_index"),
            reused_step_indices=run.get("reused_step_indices", []),
            applied_clarification_fields=run.get("applied_clarification_fields", []),
            question_rewritten=run.get("question_rewritten", False),
            overridden_plan_arguments=run.get("overridden_plan_arguments", []),
            workflow_status=run.get("workflow_status", "completed"),
            terminal_reason=run.get("terminal_reason"),
            outcome_category=run.get("outcome_category"),
            workflow_outcome=run.get("workflow_outcome"),
            recommended_next_actions=run.get("recommended_next_actions", []),
            is_recoverable=run.get("is_recoverable"),
            retry_state=run.get("retry_state"),
            recommended_recovery_action=run.get("recommended_recovery_action"),
            available_recovery_actions=run.get("available_recovery_actions", []),
            recovery_action_details=run.get("recovery_action_details", {}),
            failure_stage=run.get("failure_stage"),
            failure_message=run.get("failure_message"),
            started_at=run.get("started_at"),
            completed_at=run.get("completed_at"),
            last_updated_at=run.get("last_updated_at"),
            workflow_planning_mode=run.get("workflow_planning_mode"),
            tool_planning_mode=run.get("tool_planning_mode"),
            tool_planning_modes=run.get("tool_planning_modes", []),
            clarification_planning_mode=run.get("clarification_planning_mode"),
            planner_call_count=run.get("planner_call_count", 0),
            tool_planner_call_count=run.get("tool_planner_call_count", 0),
            workflow_planning_latency_ms=run.get("workflow_planning_latency_ms", 0),
            tool_planning_latency_ms=run.get("tool_planning_latency_ms", 0),
            clarification_planning_latency_ms=run.get("clarification_planning_latency_ms", 0),
            planner_latency_ms_total=run.get("planner_latency_ms_total", 0),
            llm_planner_layers=run.get("llm_planner_layers", []),
            fallback_planner_layers=run.get("fallback_planner_layers", []),
            llm_tool_planner_steps=run.get("llm_tool_planner_steps", []),
            fallback_tool_planner_steps=run.get("fallback_tool_planner_steps", []),
            retry_count=run.get("retry_count", 0),
            retried_step_indices=run.get("retried_step_indices", []),
            step_count=run.get("step_count", 0),
            route_type=run.get("route", {}).get("route_type", "knowledge_retrieval"),
            route_reason=run.get("route", {}).get("route_reason", ""),
            filename=run.get("filename"),
            answered_at=run.get("answered_at"),
            answer_source=run.get("answer_source"),
            workflow_family=run.get("workflow_family"),
            final_tool_name=(run.get("tool_plan") or {}).get("tool_name"),
            final_tool_action=(run.get("tool_plan") or {}).get("action"),
        )
        for run in runs
        if isinstance(run, dict) and run.get("run_id")
    ]
    return AgentWorkflowRunListResponse(runs=summaries)
