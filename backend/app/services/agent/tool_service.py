import re
import uuid
import json
from pathlib import Path

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
        "supported_actions": ["create", "update", "close", "query", "list"],
        "description": "Create, inspect, update, or close incident and ticket records for operational issues.",
        "execution_mode": "local_adapter",
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
    r"\b(create|open|close|deploy|restart|rollback|run|execute|trigger|query|update|delete|search|find|check|show|inspect|lookup|list|set|move)\b",
    re.IGNORECASE,
)
ENVIRONMENT_SEGMENT_PATTERN = re.compile(
    r"\s+\b(in|for)\s+(production|staging)\b",
    re.IGNORECASE,
)
SEARCH_PREFIX_PATTERN = re.compile(
    r"^(search|find|lookup|look up|show|inspect|query)\s+(docs?|documents?)\s+(for\s+)?",
    re.IGNORECASE,
)
GENERIC_SEARCH_PREFIX_PATTERN = re.compile(
    r"^(search|find|lookup|look up|show|inspect|query)\s+",
    re.IGNORECASE,
)
STATUS_PREFIX_PATTERN = re.compile(
    r"^(check|show|inspect|query)\s+",
    re.IGNORECASE,
)
FILENAME_PATTERN = re.compile(
    r"\b([A-Za-z0-9._-]+\.(?:txt|md|pdf|docx))\b",
    re.IGNORECASE,
)
TICKET_ID_PATTERN = re.compile(r"\b(TICKET-\d{4})\b", re.IGNORECASE)
TICKET_UPDATE_SUFFIX_PATTERN = re.compile(
    r"\b(to\s+(high|medium|low|unspecified)\s+severity"
    r"|severity\s+to\s+(high|medium|low|unspecified)"
    r"|priority\s+to\s+(high|medium|low|unspecified)"
    r"|status\s+to\s+(open|closed)"
    r"|to\s+(production|staging)"
    r"|environment\s+to\s+(production|staging))\b",
    re.IGNORECASE,
)
TICKET_DATA_DIR = Path("../data/tool_state")
TICKET_DATA_DIR.mkdir(parents=True, exist_ok=True)
TICKET_STORE_PATH = TICKET_DATA_DIR / "tickets.json"


def _extract_filename_argument(question: str) -> str | None:
    match = FILENAME_PATTERN.search(question)
    return match.group(1) if match else None


def _extract_ticket_id_argument(question: str) -> str | None:
    match = TICKET_ID_PATTERN.search(question)
    return match.group(1).upper() if match else None


def _extract_ticket_update_arguments(question: str) -> dict[str, str]:
    lowered = question.lower()
    arguments: dict[str, str] = {}

    if "high" in lowered:
        arguments["severity"] = "high"
    elif "medium" in lowered:
        arguments["severity"] = "medium"
    elif "low" in lowered:
        arguments["severity"] = "low"
    elif "unspecified" in lowered:
        arguments["severity"] = "unspecified"

    if "production" in lowered:
        arguments["environment"] = "production"
    elif "staging" in lowered:
        arguments["environment"] = "staging"

    if re.search(r"\bstatus\s+to\s+closed\b", lowered):
        arguments["status"] = "closed"
    elif re.search(r"\bstatus\s+to\s+open\b", lowered):
        arguments["status"] = "open"
    elif re.search(r"\blist\s+open\s+tickets?\b", lowered):
        arguments["status"] = "open"
    elif re.search(r"\blist\s+closed\s+tickets?\b", lowered):
        arguments["status"] = "closed"

    return arguments


def _clean_ticket_target(question: str, target: str, action: str) -> str:
    cleaned_target = target.strip()
    cleaned_target = TICKET_ID_PATTERN.sub("", cleaned_target).strip(" .")
    cleaned_target = re.sub(
        r"^(set|update|close|move)\s+",
        "",
        cleaned_target,
        flags=re.IGNORECASE,
    ).strip(" .")
    cleaned_target = re.sub(r"^(for\s+)", "", cleaned_target, flags=re.IGNORECASE).strip(" .")

    if action in {"close", "update", "query"}:
        cleaned_target = re.sub(
            r"^(ticket\s+status\s+for|ticket\s+for|ticket\s+)",
            "",
            cleaned_target,
            flags=re.IGNORECASE,
        ).strip(" .")

    if action == "update":
        cleaned_target = TICKET_UPDATE_SUFFIX_PATTERN.sub("", cleaned_target).strip(" .")

    return cleaned_target or "ticket"


def _load_ticket_store() -> list[dict[str, str]]:
    if not TICKET_STORE_PATH.exists():
        return []

    return json.loads(TICKET_STORE_PATH.read_text(encoding="utf-8"))


def _save_ticket_store(tickets: list[dict[str, str]]) -> None:
    TICKET_STORE_PATH.write_text(
        json.dumps(tickets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _find_ticket(
    tickets: list[dict[str, str]],
    target: str,
    ticket_id: str,
) -> dict[str, str] | None:
    if ticket_id:
        for ticket in tickets:
            if ticket["ticket_id"] == ticket_id:
                return ticket

    for ticket in reversed(tickets):
        if ticket["target"] == target:
            return ticket

    return None


def _run_ticketing_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    tickets = _load_ticket_store()
    target = request.target.strip()
    action = request.action.strip().lower()
    trace_id = uuid.uuid4().hex
    now = build_utc_timestamp()

    if action == "list":
        status_filter = request.arguments.get("status", "").strip().lower()
        filtered_tickets = tickets
        if status_filter:
            filtered_tickets = [
                ticket for ticket in tickets if ticket.get("status", "").lower() == status_filter
            ]

        ticket_summaries = " | ".join(
            f"{ticket['ticket_id']} [{ticket['status']}] {ticket['target']}"
            for ticket in filtered_tickets
        )
        output = {
            "ticket_count": str(len(filtered_tickets)),
            "tickets": ticket_summaries,
        }
        if status_filter:
            output["status_filter"] = status_filter

        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target or "tickets",
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Loaded {len(filtered_tickets)} local ticket(s).",
            trace_id=trace_id,
            executed_at=now,
            output=output,
        )

    if action == "create":
        ticket_id = f"TICKET-{len(tickets) + 1:04d}"
        ticket = {
            "ticket_id": ticket_id,
            "target": target,
            "status": "open",
            "severity": request.arguments.get("severity", "unspecified"),
            "environment": request.arguments.get("environment", "unspecified"),
            "created_at": now,
            "updated_at": now,
        }
        tickets.append(ticket)
        _save_ticket_store(tickets)

        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Created local ticket {ticket_id} for {target}.",
            trace_id=trace_id,
            executed_at=now,
            output=ticket,
        )

    ticket = _find_ticket(
        tickets=tickets,
        target=target,
        ticket_id=request.arguments.get("ticket_id", "").strip(),
    )
    if ticket is None:
        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="not_found",
            execution_mode="local_adapter",
            result_summary=f"No local ticket record matched {target}.",
            trace_id=trace_id,
            executed_at=now,
            output={
                "target": target,
                "ticket_id": request.arguments.get("ticket_id", "").strip(),
            },
        )

    if action == "query":
        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Loaded local ticket {ticket['ticket_id']} for {target}.",
            trace_id=trace_id,
            executed_at=now,
            output=ticket,
        )

    if action == "update":
        for key, value in request.arguments.items():
            if key == "ticket_id":
                continue
            ticket[key] = value
        ticket["updated_at"] = now
        _save_ticket_store(tickets)
        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Updated local ticket {ticket['ticket_id']} for {target}.",
            trace_id=trace_id,
            executed_at=now,
            output=ticket,
        )

    if action == "close":
        ticket["status"] = "closed"
        ticket["updated_at"] = now
        ticket["closed_at"] = now
        _save_ticket_store(tickets)
        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Closed local ticket {ticket['ticket_id']} for {target}.",
            trace_id=trace_id,
            executed_at=now,
            output=ticket,
        )

    raise ValueError("unsupported_ticket_action")


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
    if filename_filter:
        output["filename_filter"] = filename_filter
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

    if tool_name == "ticketing":
        return _run_ticketing_tool(request)

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
    action = action_match.group(1).lower() if action_match else "query"

    if "ticket" in lowered or "incident" in lowered:
        tool_name = "ticketing"
    elif any(token in lowered for token in ["status", "health", "config", "configuration"]):
        tool_name = "system_status"
        action = "query"
    else:
        tool_name = "document_search"
        action = "query"

    if tool_name == "ticketing":
        if action in {"set", "move"}:
            action = "update"
        if " for " in lowered:
            target = normalized_question.split(" for ", maxsplit=1)[1].strip()
        else:
            target = normalized_question
    elif tool_name == "system_status":
        target = STATUS_PREFIX_PATTERN.sub("", normalized_question).strip(" ?.!")
        if not target:
            target = "agent-knowledge-system"
    else:
        target = SEARCH_PREFIX_PATTERN.sub("", normalized_question).strip(" ?.!")
        target = GENERIC_SEARCH_PREFIX_PATTERN.sub("", target).strip(" ?.!")
        if not target:
            target = normalized_question.strip(" ?.!") or "documents"

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

    ticket_id = _extract_ticket_id_argument(question)
    if ticket_id:
        arguments["ticket_id"] = ticket_id

    if inferred_request.tool_name == "ticketing" and inferred_request.action in {
        "check",
        "show",
        "inspect",
        "query",
    }:
        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action="query",
            target=inferred_request.target,
        )
    elif inferred_request.tool_name == "ticketing" and inferred_request.action == "list":
        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action="list",
            target="tickets",
        )

    if inferred_request.tool_name == "ticketing":
        arguments.update(_extract_ticket_update_arguments(question))

        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action=inferred_request.action,
            target=_clean_ticket_target(question, inferred_request.target, inferred_request.action),
        )

    if inferred_request.tool_name == "document_search":
        filename = _extract_filename_argument(question)
        if filename:
            arguments["filename"] = filename

    cleaned_target = inferred_request.target
    cleaned_target = ENVIRONMENT_SEGMENT_PATTERN.sub("", cleaned_target).strip(" .")
    if inferred_request.tool_name == "document_search" and "filename" in arguments:
        cleaned_target = cleaned_target.replace(arguments["filename"], "").strip(" .")
        cleaned_target = re.sub(
            r"\b(for|in|inside|within)\b",
            "",
            cleaned_target,
            flags=re.IGNORECASE,
        ).strip(" .")
        if not cleaned_target:
            cleaned_target = "documents"

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
