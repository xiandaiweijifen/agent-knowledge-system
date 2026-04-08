"""Tool execution node — runs tool actions requested by the router."""

from app.schemas.tools import ToolExecutionRequest
from app.services.agent.tool_service import execute_tool_request, plan_tool_request
from app.services.agent_v2.state import AgentState
from app.services.ingestion.document_service import build_utc_timestamp


def _get_matching_fault_rule(state: AgentState, tool_name: str, action: str) -> dict | None:
    debug_fault_injection = state.get("debug_fault_injection") or {}
    rules = debug_fault_injection.get("tool_execution_failures", [])
    if not isinstance(rules, list):
        return None

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("tool_name") != tool_name:
            continue
        if rule.get("action") != action:
            continue
        if int(rule.get("fail_count", 0) or 0) <= 0:
            continue
        return rule
    return None


def tool_exec_node(state: AgentState) -> dict:
    """Plan and execute a single tool request using the existing tool service."""
    question = state["question"]
    started_at = build_utc_timestamp()
    tool_plan = plan_tool_request(question)
    fault_rule = _get_matching_fault_rule(state, tool_plan.tool_name, tool_plan.action)
    if fault_rule is not None:
        failure_message = str(fault_rule.get("message") or "debug injected tool execution failure")
        return {
            "tool_chain": [
                {
                    "step_id": "step_1",
                    "step_index": 1,
                    "step_status": "failed",
                    "attempt_count": 1,
                    "retried": False,
                    "started_at": started_at,
                    "completed_at": build_utc_timestamp(),
                    "question": question,
                    "tool_plan": tool_plan.model_dump(),
                    "tool_execution": None,
                    "failure_message": failure_message,
                }
            ],
            "workflow_status": "failed",
            "failure_stage": "tool_execution",
            "retry_state": "retry_exhausted",
            "retry_count": 1,
            "error": failure_message,
        }
    execution_request = ToolExecutionRequest(
        tool_name=tool_plan.tool_name,
        action=tool_plan.action,
        target=tool_plan.target,
        arguments=tool_plan.arguments,
    )
    try:
        tool_execution = execute_tool_request(execution_request)
    except Exception as exc:
        failure_message = str(exc)
        return {
            "tool_chain": [
                {
                    "step_id": "step_1",
                    "step_index": 1,
                    "step_status": "failed",
                    "attempt_count": 1,
                    "retried": False,
                    "started_at": started_at,
                    "completed_at": build_utc_timestamp(),
                    "question": question,
                    "tool_plan": tool_plan.model_dump(),
                    "tool_execution": None,
                    "failure_message": failure_message,
                }
            ],
            "workflow_status": "failed",
            "failure_stage": "tool_execution",
            "retry_state": "retry_exhausted",
            "retry_count": 1,
            "error": failure_message,
        }
    step_record = {
        "step_id": "step_1",
        "step_index": 1,
        "step_status": tool_execution.execution_status,
        "attempt_count": 1,
        "retried": False,
        "started_at": started_at,
        "completed_at": tool_execution.executed_at,
        "question": question,
        "tool_plan": tool_plan.model_dump(),
        "tool_execution": tool_execution.model_dump(),
        "failure_message": None,
    }

    return {
        "tool_chain": [step_record],
        "answer": tool_execution.result_summary,
        "answer_source": "tool_result",
        "workflow_status": "completed",
        "failure_stage": None,
        "retry_state": "not_applicable",
        "retry_count": 0,
    }
