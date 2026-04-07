"""Tool execution node — runs tool actions requested by the router."""

from app.schemas.tools import ToolExecutionRequest
from app.services.agent.tool_service import execute_tool_request, plan_tool_request
from app.services.agent_v2.state import AgentState
from app.services.ingestion.document_service import build_utc_timestamp


def tool_exec_node(state: AgentState) -> dict:
    """Plan and execute a single tool request using the existing tool service."""
    question = state["question"]
    started_at = build_utc_timestamp()
    tool_plan = plan_tool_request(question)
    execution_request = ToolExecutionRequest(
        tool_name=tool_plan.tool_name,
        action=tool_plan.action,
        target=tool_plan.target,
        arguments=tool_plan.arguments,
    )
    tool_execution = execute_tool_request(execution_request)
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
    }
