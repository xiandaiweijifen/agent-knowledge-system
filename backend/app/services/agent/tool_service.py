import re
import uuid

from app.core.config import settings
from app.schemas.tools import (
    InferredToolRequest,
    ToolCatalogEntry,
    ToolCatalogResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolPlanResponse,
)
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.ingestion import document_service


SUPPORTED_TOOLS: dict[str, dict[str, object]] = {
    "ticketing": {
        "supported_actions": ["create", "update", "close"],
        "description": "Create or update incident and ticket records for operational issues.",
        "execution_mode": "local_stub",
    },
    "system_status": {
        "supported_actions": ["query"],
        "description": "Inspect service or system health status through a status-style tool interface.",
        "execution_mode": "local_adapter",
    },
    "document_search": {
        "supported_actions": ["query"],
        "description": "Perform a tool-style document lookup outside the main retrieval answer flow.",
        "execution_mode": "local_adapter",
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


def _build_system_status_output() -> dict[str, str]:
    embedding_model = (
        settings.gemini_embedding_model
        if settings.embedding_provider == "gemini"
        else settings.openai_embedding_model
        if settings.embedding_provider == "openai"
        else "mock-embedding-v1"
    )
    chat_model = (
        settings.gemini_chat_model
        if settings.chat_provider == "gemini"
        else settings.openai_chat_model
        if settings.chat_provider == "openai"
        else "local-fallback"
    )

    return {
        "status": "ok",
        "app_env": settings.app_env,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": embedding_model,
        "chat_provider": settings.chat_provider,
        "chat_model": chat_model,
        "gemini_configured": str(bool(settings.gemini_api_key)).lower(),
        "openai_configured": str(bool(settings.openai_api_key)).lower(),
        "database_configured": str(bool(settings.database_url)).lower(),
        "redis_configured": str(bool(settings.redis_url)).lower(),
    }


def _run_document_search_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    query = request.target.strip()
    filename_filter = request.arguments.get("filename", "").strip()
    trace_id = uuid.uuid4().hex

    documents = document_service.list_documents()
    if filename_filter:
        documents = [item for item in documents if item["filename"] == filename_filter]

    matched_documents: list[str] = []
    preview_snippets: list[str] = []
    skipped_documents = 0

    for item in documents:
        try:
            preview = document_service.read_text_document(item["filename"])
        except FileNotFoundError:
            continue
        except ValueError as exc:
            if str(exc) in {"unsupported_file_type", "text_decode_error"}:
                skipped_documents += 1
                continue
            raise

        content = preview["content"]
        lowered_content = content.lower()
        lowered_query = query.lower()

        if lowered_query not in lowered_content:
            continue

        matched_documents.append(item["filename"])
        first_index = lowered_content.index(lowered_query)
        snippet_start = max(0, first_index - 40)
        snippet_end = min(len(content), first_index + len(query) + 80)
        snippet = content[snippet_start:snippet_end].replace("\n", " ").strip()
        preview_snippets.append(f'{item["filename"]}: {snippet}')

    result_summary = (
        f"Found {len(matched_documents)} matching document(s) for '{query}'."
        if matched_documents
        else f"No documents matched '{query}'."
    )

    output: dict[str, str] = {
        "query": query,
        "matched_count": str(len(matched_documents)),
        "matched_documents": ", ".join(matched_documents),
        "skipped_documents": str(skipped_documents),
    }
    if preview_snippets:
        output["snippets"] = " | ".join(preview_snippets[:3])

    return ToolExecutionResponse(
        tool_name="document_search",
        action=request.action,
        target=query,
        execution_status="completed",
        execution_mode="local_adapter",
        result_summary=result_summary,
        trace_id=trace_id,
        executed_at=build_utc_timestamp(),
        output=output,
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

    if tool_name == "system_status":
        output = _build_system_status_output()
        return ToolExecutionResponse(
            tool_name=tool_name,
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=(
                f"Collected local system status for {target or 'agent-knowledge-system'}."
            ),
            trace_id=uuid.uuid4().hex,
            executed_at=build_utc_timestamp(),
            output=output,
        )

    if tool_name == "document_search":
        return _run_document_search_tool(request)

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
