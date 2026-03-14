import re
import uuid

from app.schemas.tools import InferredToolRequest, ToolExecutionRequest, ToolExecutionResponse
from app.services.ingestion.document_service import build_utc_timestamp


SUPPORTED_TOOLS = {
    "ticketing",
    "system_status",
    "document_search",
}
ACTION_PATTERN = re.compile(
    r"\b(create|open|close|deploy|restart|rollback|run|execute|trigger|query|update|delete)\b",
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
