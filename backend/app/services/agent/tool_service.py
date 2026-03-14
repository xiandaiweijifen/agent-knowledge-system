import re
import uuid

from app.schemas.tools import (
    InferredToolRequest,
    ToolCatalogEntry,
    ToolCatalogResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolPlanResponse,
)
from app.services.ingestion.document_service import build_utc_timestamp


SUPPORTED_TOOLS: dict[str, dict[str, object]] = {
    "ticketing": {
        "supported_actions": ["create", "update", "close"],
        "description": "Create or update incident and ticket records for operational issues.",
        "execution_mode": "local_stub",
    },
    "system_status": {
        "supported_actions": ["query"],
        "description": "Inspect service or system health status through a status-style tool interface.",
        "execution_mode": "local_stub",
    },
    "document_search": {
        "supported_actions": ["query"],
        "description": "Perform a tool-style document lookup outside the main retrieval answer flow.",
        "execution_mode": "local_stub",
    },
}
ACTION_PATTERN = re.compile(
    r"\b(create|open|close|deploy|restart|rollback|run|execute|trigger|query|update|delete)\b",
    re.IGNORECASE,
)
ENVIRONMENT_SEGMENT_PATTERN = re.compile(
    r"\s+\b(in|for)\s+(production|staging)\b",
    re.IGNORECASE,
)


def execute_tool_request(request: ToolExecutionRequest) -> ToolExecutionResponse:
    """Execute a minimal local tool stub for workflow integration."""
    tool_name = request.tool_name.strip().lower()
    action = request.action.strip().lower()
    target = request.target.strip()

    if not tool_name or not action or not target:
        raise ValueError("tool_request_fields_must_not_be_empty")

    if tool_name not in SUPPORTED_TOOLS:
        raise ValueError("unsupported_tool_name")

    trace_id = uuid.uuid4().hex

    return ToolExecutionResponse(
        tool_name=tool_name,
        action=action,
        target=target,
        execution_status="stubbed",
        execution_mode="local_stub",
        result_summary=(
            f"Stubbed tool execution recorded for {tool_name}:{action} on {target}. "
            "No external side effects were triggered."
        ),
        trace_id=trace_id,
        executed_at=build_utc_timestamp(),
        output={
            "target": target,
            "action": action,
            "note": "Replace this stub with a real tool adapter in the next iteration.",
        },
    )


def list_registered_tools() -> ToolCatalogResponse:
    """Return the currently registered tool catalog."""
    tools = [
        ToolCatalogEntry(
            tool_name=tool_name,
            supported_actions=list(tool_config["supported_actions"]),
            description=str(tool_config["description"]),
            execution_mode=str(tool_config["execution_mode"]),
        )
        for tool_name, tool_config in SUPPORTED_TOOLS.items()
    ]
    return ToolCatalogResponse(
        count=len(tools),
        tools=tools,
    )


def infer_tool_request(question: str) -> InferredToolRequest:
    """Infer a minimal tool request from a routed execution query."""
    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("question_must_not_be_empty")

    lowered = normalized_question.lower()
    action_match = ACTION_PATTERN.search(lowered)
    action = action_match.group(1).lower() if action_match else "execute"

    if "ticket" in lowered or "incident" in lowered:
        tool_name = "ticketing"
    elif "status" in lowered:
        tool_name = "system_status"
    else:
        tool_name = "document_search"

    if " for " in lowered:
        target = normalized_question.split(" for ", maxsplit=1)[1].strip()
    else:
        target = normalized_question

    return InferredToolRequest(
        tool_name=tool_name,
        action=action,
        target=target,
    )


def plan_tool_request(question: str) -> ToolPlanResponse:
    """Create a structured tool plan from a natural-language tool request."""
    inferred_request = infer_tool_request(question)
    lowered = question.lower()
    arguments: dict[str, str] = {}

    if "high" in lowered:
        arguments["severity"] = "high"
    elif "medium" in lowered:
        arguments["severity"] = "medium"
    elif "low" in lowered:
        arguments["severity"] = "low"

    if "production" in lowered:
        arguments["environment"] = "production"
    elif "staging" in lowered:
        arguments["environment"] = "staging"

    cleaned_target = inferred_request.target
    cleaned_target = ENVIRONMENT_SEGMENT_PATTERN.sub("", cleaned_target).strip(" .")

    return ToolPlanResponse(
        question=question.strip(),
        planning_mode="heuristic_stub",
        route_hint="tool_execution",
        tool_name=inferred_request.tool_name,
        action=inferred_request.action,
        target=cleaned_target,
        arguments=arguments,
        plan_summary=(
            f"Plan {inferred_request.tool_name}:{inferred_request.action} for "
            f"{cleaned_target} using a local heuristic planner."
        ),
    )
