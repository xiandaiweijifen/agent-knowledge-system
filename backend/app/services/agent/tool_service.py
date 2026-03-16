import re
import uuid
import json
import unicodedata
from pathlib import Path
from typing import Any

from app.core.config import DATA_ROOT
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
from app.services.agent.state_store import JsonListRepository
from app.services.llm.tool_planner_service import generate_llm_tool_plan


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
    r"\s+\b(in|for)\s+(production|staging|development|dev)\b",
    re.IGNORECASE,
)
ENVIRONMENT_ARGUMENT_PATTERN = re.compile(
    r"\b(?:in|for|to)\s+(production|staging|development|dev)\b"
    r"|\benvironment\s+to\s+(production|staging|development|dev)\b",
    re.IGNORECASE,
)
SEARCH_PREFIX_PATTERN = re.compile(
    r"^(search|find|lookup|look up|show|inspect|query)\s+(docs?|documents?)\s+((for|about)\s+)?",
    re.IGNORECASE,
)
GENERIC_SEARCH_PREFIX_PATTERN = re.compile(
    r"^(search|find|lookup|look up|show|inspect|query)\s+",
    re.IGNORECASE,
)
RESULT_LIMIT_PATTERN = re.compile(
    r"\b(?:and\s+show\s+)?top\s+(\d+)\s+results?\b"
    r"|\b(?:and\s+show\s+)?first\s+(\d+)\s+results?\b"
    r"|\blimit(?:ed)?(?:\s+results?)?\s+to\s+(\d+)\b"
    r"|\blimit\s+(\d+)\s+results?\b",
    re.IGNORECASE,
)
STATUS_PREFIX_PATTERN = re.compile(
    r"^(check|show|inspect|query)\s+",
    re.IGNORECASE,
)
SYSTEM_STATUS_FOR_PATTERN = re.compile(
    r"^(system\s+status|status|health|configuration|config)\s+for\s+",
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
TICKET_LIST_TARGET_PATTERN = re.compile(
    r"\blist\b.+?\btickets?\b\s+for\s+(?P<target>.+)$",
    re.IGNORECASE,
)
TICKET_DATA_DIR = DATA_ROOT / "tool_state"
TICKET_DATA_DIR.mkdir(parents=True, exist_ok=True)
TICKET_STORE_PATH = TICKET_DATA_DIR / "tickets.json"
TOOL_OUTPUT_SCHEMA_VERSION = "tool-output-v1"


def _build_tool_output_metadata(
    *,
    output_kind: str,
    resource_type: str,
    target: str,
    item_count: int | None = None,
    resource_id: str | None = None,
) -> dict[str, str]:
    metadata = {
        "schema_version": TOOL_OUTPUT_SCHEMA_VERSION,
        "output_kind": output_kind,
        "resource_type": resource_type,
        "target": target,
    }
    if item_count is not None:
        metadata["item_count"] = str(item_count)
    if resource_id:
        metadata["resource_id"] = resource_id
    return metadata


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

    normalized_environment = _extract_environment_argument(question)
    if normalized_environment:
        arguments["environment"] = normalized_environment

    if re.search(r"\bstatus\s+to\s+closed\b", lowered):
        arguments["status"] = "closed"
    elif re.search(r"\bstatus\s+to\s+open\b", lowered):
        arguments["status"] = "open"
    elif re.search(r"\blist\b.+\bopen\s+tickets?\b", lowered):
        arguments["status"] = "open"
    elif re.search(r"\blist\b.+\bclosed\s+tickets?\b", lowered):
        arguments["status"] = "closed"

    return arguments


def _canonicalize_ticket_target(target: str) -> str:
    cleaned_target = target.strip().lower()
    if not cleaned_target:
        return "ticket"

    cleaned_target = TICKET_ID_PATTERN.sub("", cleaned_target).strip(" .")
    cleaned_target = re.sub(r"^(?:a|an|the)\s+", "", cleaned_target).strip()
    cleaned_target = re.sub(
        r"\b(?:outage|incident|issue|problem|alert|failure)s?\b$",
        "",
        cleaned_target,
        flags=re.IGNORECASE,
    ).strip(" .")
    cleaned_target = re.sub(r"\s+", " ", cleaned_target)

    if not cleaned_target:
        return "ticket"

    if "-" in cleaned_target and " " not in cleaned_target:
        return cleaned_target

    return cleaned_target.replace(" ", "-")


def _extract_ticket_target_filter(question: str) -> str | None:
    match = TICKET_LIST_TARGET_PATTERN.search(question.strip())
    if not match:
        return None
    target = ENVIRONMENT_SEGMENT_PATTERN.sub("", match.group("target")).strip(" .")
    target = RESULT_LIMIT_PATTERN.sub("", target).strip(" .")
    target = re.sub(r"\band\s+show\b", "", target, flags=re.IGNORECASE).strip(" .")
    return _canonicalize_ticket_target(target)


def _normalize_environment_value(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "dev":
        return "development"
    return normalized


def _extract_environment_argument(question: str) -> str | None:
    match = ENVIRONMENT_ARGUMENT_PATTERN.search(question)
    if not match:
        return None
    for group in match.groups():
        if group:
            return _normalize_environment_value(group)
    return None


def _is_generic_ticket_target(target: str) -> bool:
    return target.strip().lower() in {"ticket", "tickets", "incident", "incidents"}


def _pop_ticket_target_argument(arguments: dict[str, str]) -> str | None:
    for key in ("service", "service_name", "target", "resource"):
        value = arguments.get(key, "").strip()
        if value:
            arguments.pop(key, None)
            return value
    return None


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

    cleaned_target = ENVIRONMENT_SEGMENT_PATTERN.sub("", cleaned_target).strip(" .")

    return _canonicalize_ticket_target(cleaned_target or "ticket")


def _load_ticket_store() -> list[dict[str, Any]]:
    return JsonListRepository(
        TICKET_STORE_PATH,
        normalizer=_normalize_ticket_record,
    ).load()


def _save_ticket_store(tickets: list[dict[str, Any]]) -> None:
    JsonListRepository(
        TICKET_STORE_PATH,
        normalizer=_normalize_ticket_record,
    ).save(tickets)


def _normalize_ticket_record(ticket: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(ticket)
    ticket_id = normalized.get("ticket_id", "").strip()
    target = _canonicalize_ticket_target(normalized.get("target", "").strip() or "ticket")
    normalized["target"] = target
    normalized.update(
        _build_tool_output_metadata(
            output_kind="record",
            resource_type="ticket",
            target=target,
            resource_id=ticket_id or None,
        )
    )
    return normalized


def _build_ticket_collection_records(tickets: list[dict[str, Any]]) -> list[dict[str, str]]:
    serialized_records: list[dict[str, str]] = []
    for ticket in tickets:
        serialized_records.append(
            {
                "ticket_id": ticket.get("ticket_id", ""),
                "target": ticket.get("target", ""),
                "status": ticket.get("status", ""),
                "severity": ticket.get("severity", ""),
                "environment": ticket.get("environment", ""),
            }
        )
    return serialized_records


def _sort_tickets_by_latest(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        tickets,
        key=lambda ticket: (
            ticket.get("updated_at", "") or ticket.get("created_at", ""),
            ticket.get("ticket_id", ""),
        ),
        reverse=True,
    )


def _find_ticket(
    tickets: list[dict[str, Any]],
    target: str,
    ticket_id: str,
) -> dict[str, Any] | None:
    if ticket_id:
        for ticket in tickets:
            if ticket["ticket_id"] == ticket_id:
                return ticket

    for ticket in reversed(tickets):
        if ticket["target"] == target:
            return ticket

    return None


def _build_supporting_summary(arguments: dict[str, str]) -> str:
    query = arguments.get("supporting_query", "").strip()
    matched_documents = arguments.get("supporting_documents", "").strip()
    matched_count = arguments.get("supporting_match_count", "").strip()
    snippets = arguments.get("supporting_snippets", "").strip()
    supporting_status = arguments.get("supporting_status", "").strip()
    supporting_status_target = arguments.get("supporting_status_target", "").strip()
    supporting_status_app_env = arguments.get("supporting_status_app_env", "").strip()
    supporting_status_requested_env = arguments.get("supporting_status_requested_env", "").strip()

    summary_parts: list[str] = []

    if matched_count and query:
        summary_parts.append(
            f"Search for '{query}' matched {matched_count} supporting document(s)."
        )
    elif query:
        summary_parts.append(f"Search context came from query '{query}'.")

    if matched_documents:
        primary_documents = ", ".join(
            item.strip() for item in matched_documents.split(",")[:2] if item.strip()
        )
        if primary_documents:
            summary_parts.append(f"Primary supporting documents: {primary_documents}.")

    if snippets:
        first_snippet = snippets.split(" | ", maxsplit=1)[0].strip()
        if first_snippet:
            summary_parts.append(f"Top supporting snippet: {first_snippet}")

    if supporting_status:
        status_subject = supporting_status_target or "the requested target"
        status_sentence = (
            f"System status snapshot for {status_subject} reported status {supporting_status}"
        )
        if supporting_status_app_env:
            status_sentence += f" in {supporting_status_app_env}"
        if supporting_status_requested_env:
            status_sentence += f" for requested {supporting_status_requested_env}"
        summary_parts.append(f"{status_sentence}.")

    return " ".join(summary_parts).strip()


def _tokenize_search_terms(query: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", query.lower()) if token]


def _normalize_search_excerpt(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("\ufffd", " ")
    cleaned = "".join(
        " " if unicodedata.category(char).startswith("C") and char not in {" ", "\t"} else char
        for char in cleaned
    )
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"[•●▪◦■□◆◇►▸▹▶]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.strip(" -|")


def _is_heading_like_excerpt(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    if re.match(r"^#{1,6}\s+\S+", stripped):
        return True

    if len(stripped) < 28 and stripped == stripped.title() and "." not in stripped:
        return True

    return False


def _candidate_search_segments(content: str) -> list[tuple[int, str]]:
    segments: list[tuple[int, str]] = []
    start = 0

    for match in re.finditer(r"\n\s*\n", content):
        end = match.start()
        segment = content[start:end].strip()
        if segment:
            segments.append((start, segment))
        start = match.end()

    trailing = content[start:].strip()
    if trailing:
        segments.append((start, trailing))

    return segments


def _split_search_sentences(text: str) -> list[str]:
    normalized = _normalize_search_excerpt(text)
    if not normalized:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?。！？])\s+(?=[A-Z0-9])", normalized)
        if sentence.strip()
    ]


def _strip_heading_lines(segment: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in segment.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s+\S+", line):
            continue
        if len(line) < 28 and line == line.title() and "." not in line:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _select_segment_evidence_sentence(segment: str, query: str) -> str:
    normalized_segment = _ensure_sentence_boundary_excerpt(_strip_heading_lines(segment))
    if not normalized_segment or _is_heading_like_excerpt(normalized_segment):
        return ""

    sentences = _split_search_sentences(normalized_segment)
    if not sentences:
        return normalized_segment

    lowered_query = query.lower()
    query_terms = _tokenize_search_terms(query)

    for sentence in sentences:
        if lowered_query in sentence.lower():
            return sentence

    for sentence in sentences:
        lowered_sentence = sentence.lower()
        if any(term in lowered_sentence for term in query_terms):
            return sentence

    return sentences[0]


def _find_segment_evidence_snippet(content: str, first_index: int, query: str) -> str:
    for segment_start, segment in _candidate_search_segments(content):
        segment_end = segment_start + len(segment)
        if segment_end < first_index:
            continue

        evidence_sentence = _select_segment_evidence_sentence(segment, query)
        if not evidence_sentence:
            continue

        lowered_sentence = evidence_sentence.lower()
        lowered_query = query.lower()
        if lowered_query in lowered_sentence:
            return evidence_sentence

        if any(term in lowered_sentence for term in _tokenize_search_terms(query)):
            return evidence_sentence

    return ""


def _ensure_sentence_boundary_excerpt(text: str) -> str:
    cleaned = _normalize_search_excerpt(text)
    if not cleaned:
        return cleaned

    cleaned = re.sub(
        r"^[A-Z][A-Za-z-]{2,40}\s+(?=(The|This|A|An|Many|In|When|RAG)\b)",
        "",
        cleaned,
    ).strip()

    # If a snippet starts mid-word, drop the leading fragment up to the next space.
    if cleaned and cleaned[0].isalnum() and not cleaned.startswith(("RAG", "Retrieval", "Reranking")):
        first_space = cleaned.find(" ")
        if 0 < first_space < 24:
            candidate = cleaned[first_space + 1 :].strip()
            if candidate and candidate[0].isupper():
                cleaned = candidate

    return cleaned


def _extract_search_snippet(content: str, first_index: int, query: str) -> str:
    snippet_start = max(0, first_index - 120)
    snippet_end = min(len(content), first_index + len(query) + 180)

    local_start = first_index
    for index in range(first_index, snippet_start, -1):
        if content[index - 1] in ".!?銆俓n":
            local_start = index
            break

    local_end = snippet_end
    for index in range(first_index + len(query), snippet_end):
        if content[index] in ".!?銆俓n":
            local_end = index + 1
            break

    snippet = _ensure_sentence_boundary_excerpt(content[local_start:local_end])
    min_length = max(36, len(query) + 8)
    segment_evidence = _find_segment_evidence_snippet(content, first_index, query)

    if segment_evidence and (
        _is_heading_like_excerpt(snippet)
        or len(snippet) < min_length
        or "##" in snippet
        or snippet.count(" ") < 5
        or not re.search(r"[.!?。！？]$", snippet)
    ):
        snippet = segment_evidence

    if segment_evidence and snippet != segment_evidence:
        snippet = segment_evidence

    if len(snippet) > 220:
        snippet = f"{snippet[:217].rstrip()}..."

    return snippet


def _score_document_search_match(
    filename: str,
    content: str,
    query: str,
    first_index: int,
) -> tuple[float, str, str]:
    lowered_filename = filename.lower()
    lowered_content = content.lower()
    lowered_query = query.lower()
    query_terms = _tokenize_search_terms(query)

    score = 0.0
    reasons: list[str] = []

    if lowered_query in lowered_filename:
        score += 4.0
        reasons.append("filename match")

    if lowered_query in lowered_content:
        score += 3.0
        reasons.append("full query match")

    early_occurrence_bonus = max(0.0, 1.5 - min(first_index, 600) / 400)
    score += early_occurrence_bonus
    if early_occurrence_bonus > 0:
        reasons.append("early occurrence")

    if query_terms:
        matched_terms = sum(1 for term in query_terms if term in lowered_content)
        term_coverage_bonus = matched_terms / len(query_terms)
        score += term_coverage_bonus
        if matched_terms:
            reasons.append(f"term coverage {matched_terms}/{len(query_terms)}")

    snippet = _extract_search_snippet(content, first_index, query)

    return score, f"{filename}: {snippet}", ", ".join(reasons)


def _parse_max_results_argument(arguments: dict[str, str]) -> int | None:
    raw_value = arguments.get("max_results", "").strip()
    if not raw_value:
        return None

    try:
        max_results = int(raw_value)
    except ValueError:
        return None

    if max_results <= 0:
        return None

    return max_results


def _extract_search_max_results_argument(question: str) -> str | None:
    match = RESULT_LIMIT_PATTERN.search(question)
    if not match:
        return None

    for group in match.groups():
        if group:
            return group

    return None


def _run_ticketing_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    tickets = _load_ticket_store()
    target = request.target.strip()
    action = request.action.strip().lower()
    trace_id = uuid.uuid4().hex
    now = build_utc_timestamp()

    if action == "list":
        status_filter = request.arguments.get("status", "").strip().lower()
        target_filter = _canonicalize_ticket_target(
            request.arguments.get("target_filter", "").strip()
        ) if request.arguments.get("target_filter", "").strip() else ""
        severity_filter = request.arguments.get("severity_filter", "").strip().lower()
        environment_filter = request.arguments.get("environment_filter", "").strip().lower()
        max_results = _parse_max_results_argument(request.arguments)
        filtered_tickets = tickets
        if status_filter:
            filtered_tickets = [
                ticket for ticket in tickets if ticket.get("status", "").lower() == status_filter
            ]
        if target_filter:
            filtered_tickets = [
                ticket
                for ticket in filtered_tickets
                if _canonicalize_ticket_target(ticket.get("target", "")) == target_filter
            ]
        if severity_filter:
            filtered_tickets = [
                ticket
                for ticket in filtered_tickets
                if ticket.get("severity", "").lower() == severity_filter
            ]
        if environment_filter:
            filtered_tickets = [
                ticket
                for ticket in filtered_tickets
                if ticket.get("environment", "").lower() == environment_filter
            ]
        filtered_count = len(filtered_tickets)
        filtered_tickets = _sort_tickets_by_latest(filtered_tickets)
        returned_tickets = filtered_tickets[:max_results] if max_results else filtered_tickets

        ticket_summaries = " | ".join(
            f"{ticket['ticket_id']} [{ticket['status']}] {ticket['target']}"
            for ticket in returned_tickets
        )
        ticket_records = _build_ticket_collection_records(returned_tickets)
        output: dict[str, Any] = {
            **_build_tool_output_metadata(
                output_kind="collection",
                resource_type="ticket",
                target=target or "tickets",
                item_count=len(returned_tickets),
            ),
            "ticket_count": str(len(returned_tickets)),
            "matched_count": str(filtered_count),
            "tickets": ticket_summaries,
            "ticket_ids": ", ".join(ticket["ticket_id"] for ticket in returned_tickets),
            "tickets_json": json.dumps(ticket_records, ensure_ascii=False),
            "ticket_records": ticket_records,
            "sort_by": "updated_at",
            "sort_order": "desc",
        }
        if status_filter:
            output["status_filter"] = status_filter
        if target_filter:
            output["target_filter"] = target_filter
        if severity_filter:
            output["severity_filter"] = severity_filter
        if environment_filter:
            output["environment_filter"] = environment_filter
        if max_results:
            output["max_results"] = str(max_results)

        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target or "tickets",
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Loaded {len(returned_tickets)} local ticket(s).",
            trace_id=trace_id,
            executed_at=now,
            output=output,
        )

    if action == "create":
        ticket_id = f"TICKET-{len(tickets) + 1:04d}"
        ticket = {
            **_build_tool_output_metadata(
                output_kind="record",
                resource_type="ticket",
                target=target,
                resource_id=ticket_id,
            ),
            "ticket_id": ticket_id,
            "target": target,
            "status": "open",
            "severity": request.arguments.get("severity", "unspecified"),
            "environment": request.arguments.get("environment", "unspecified"),
            "created_at": now,
            "updated_at": now,
        }
        for context_key in (
            "supporting_query",
            "supporting_documents",
            "supporting_snippets",
            "supporting_match_count",
            "supporting_status",
            "supporting_status_target",
            "supporting_status_app_env",
        ):
            context_value = request.arguments.get(context_key, "").strip()
            if context_value:
                ticket[context_key] = context_value
        supporting_summary = (
            request.arguments.get("supporting_summary", "").strip()
            or _build_supporting_summary(request.arguments)
        )
        if supporting_summary:
            ticket["supporting_summary"] = supporting_summary
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
                **_build_tool_output_metadata(
                    output_kind="record",
                    resource_type="ticket",
                    target=target,
                ),
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
        supporting_summary = (
            request.arguments.get("supporting_summary", "").strip()
            or _build_supporting_summary(request.arguments)
        )
        if supporting_summary:
            ticket["supporting_summary"] = supporting_summary
        normalized_status = request.arguments.get("status", "").strip().lower()
        if normalized_status == "open":
            ticket.pop("closed_at", None)
        elif normalized_status == "closed":
            ticket["closed_at"] = now
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
        for key, value in request.arguments.items():
            if key == "ticket_id":
                continue
            ticket[key] = value
        supporting_summary = (
            request.arguments.get("supporting_summary", "").strip()
            or _build_supporting_summary(request.arguments)
        )
        if supporting_summary:
            ticket["supporting_summary"] = supporting_summary
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


def _build_system_status_output(target: str, requested_environment: str = "") -> dict[str, str]:
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

    output = {
        **_build_tool_output_metadata(
            output_kind="status_snapshot",
            resource_type="system_status",
            target=target,
        ),
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
    if requested_environment:
        output["requested_environment"] = requested_environment
    return output


def _run_document_search_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    query = request.target.strip()
    filename_filter = request.arguments.get("filename", "").strip()
    max_results = _parse_max_results_argument(request.arguments)
    trace_id = uuid.uuid4().hex

    documents = document_service.list_documents()
    if filename_filter:
        documents = [item for item in documents if item["filename"] == filename_filter]

    ranked_matches: list[tuple[float, str, str, str]] = []
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

        first_index = lowered_content.index(lowered_query)
        score, snippet, reason = _score_document_search_match(
            filename=item["filename"],
            content=content,
            query=query,
            first_index=first_index,
        )
        ranked_matches.append((score, item["filename"], snippet, reason))

    ranked_matches.sort(key=lambda item: (-item[0], item[1]))
    returned_matches = ranked_matches[:max_results] if max_results else ranked_matches
    matched_documents = [filename for _, filename, _, _ in returned_matches]
    preview_snippets = [snippet for _, _, snippet, _ in returned_matches]

    result_summary = (
        f"Found {len(matched_documents)} matching document(s) for '{query}'."
        if matched_documents
        else f"No documents matched '{query}'."
    )

    output: dict[str, Any] = {
        **_build_tool_output_metadata(
            output_kind="search_results",
            resource_type="document_match",
            target=query,
            item_count=len(returned_matches),
        ),
        "query": query,
        "matched_count": str(len(ranked_matches)),
        "returned_count": str(len(returned_matches)),
        "matched_documents": ", ".join(matched_documents),
        "skipped_documents": str(skipped_documents),
    }
    if filename_filter:
        output["filename_filter"] = filename_filter
    if max_results:
        output["max_results"] = str(max_results)
    if preview_snippets:
        output["snippets"] = " | ".join(preview_snippets[:3])
    if ranked_matches:
        top_score, top_filename, _, top_reason = ranked_matches[0]
        output["top_match_document"] = top_filename
        output["top_match_score"] = f"{top_score:.3f}"
        output["top_match_reason"] = top_reason or "content match"

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
        requested_environment = _normalize_environment_value(
            request.arguments.get("environment", "").strip()
        )
        output = _build_system_status_output(target, requested_environment=requested_environment)
        return ToolExecutionResponse(
            tool_name=tool_name,
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=(
                f"Collected local system status for {target or 'agent-knowledge-system'}"
                + (
                    f" with requested environment {requested_environment}."
                    if requested_environment
                    else "."
                )
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
        target = SYSTEM_STATUS_FOR_PATTERN.sub("", target).strip(" ?.!")
        target = ENVIRONMENT_SEGMENT_PATTERN.sub("", target).strip(" ?.!")
        if not target:
            target = "agent-knowledge-system"
    else:
        target = SEARCH_PREFIX_PATTERN.sub("", normalized_question).strip(" ?.!")
        target = GENERIC_SEARCH_PREFIX_PATTERN.sub("", target).strip(" ?.!")
        target = re.sub(r"^about\s+", "", target, flags=re.IGNORECASE).strip(" ?.!")
        if not target:
            target = normalized_question.strip(" ?.!") or "documents"

    return InferredToolRequest(
        tool_name=tool_name,
        action=action,
        target=target,
    )


def _build_tool_plan_response(
    *,
    question: str,
    inferred_request: InferredToolRequest,
    arguments: dict[str, str],
    planning_mode: str,
) -> ToolPlanResponse:
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
    if inferred_request.tool_name == "document_search" and "max_results" in arguments:
        cleaned_target = RESULT_LIMIT_PATTERN.sub("", cleaned_target).strip(" .")
        cleaned_target = re.sub(r"\band\s+show\b", "", cleaned_target, flags=re.IGNORECASE).strip(" .")
        if not cleaned_target:
            cleaned_target = "documents"

    planner_label = "llm planner" if planning_mode.startswith("llm_") else "local heuristic planner"

    return ToolPlanResponse(
        question=question.strip(),
        planning_mode=planning_mode,
        route_hint="tool_execution",
        tool_name=inferred_request.tool_name,
        action=inferred_request.action,
        target=cleaned_target,
        arguments=arguments,
        plan_summary=(
            f"Plan {inferred_request.tool_name}:{inferred_request.action} for "
            f"{cleaned_target} using a {planner_label}."
        ),
    )


def _normalize_planned_request(
    question: str,
    inferred_request: InferredToolRequest,
    arguments: dict[str, str],
) -> tuple[InferredToolRequest, dict[str, str]]:
    normalized_arguments = dict(arguments)

    ticket_id = _extract_ticket_id_argument(question)
    if ticket_id and "ticket_id" not in normalized_arguments:
        normalized_arguments["ticket_id"] = ticket_id

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
        extracted_ticket_arguments = _extract_ticket_update_arguments(question)
        for key, value in extracted_ticket_arguments.items():
            normalized_arguments.setdefault(key, value)
        if inferred_request.action == "list":
            if "severity" in normalized_arguments:
                normalized_arguments["severity_filter"] = normalized_arguments.pop("severity")
            if "environment" in normalized_arguments:
                normalized_arguments["environment_filter"] = normalized_arguments.pop("environment")
            target_filter = _extract_ticket_target_filter(question)
            if target_filter and "target_filter" not in normalized_arguments:
                normalized_arguments["target_filter"] = target_filter
            max_results = _extract_search_max_results_argument(question)
            if max_results and "max_results" not in normalized_arguments:
                normalized_arguments["max_results"] = max_results
        cleaned_ticket_target = _clean_ticket_target(
            question,
            inferred_request.target,
            inferred_request.action,
        )
        if _is_generic_ticket_target(cleaned_ticket_target):
            argument_target = _pop_ticket_target_argument(normalized_arguments)
            if argument_target:
                cleaned_ticket_target = _canonicalize_ticket_target(argument_target)

        inferred_request = InferredToolRequest(
            tool_name=inferred_request.tool_name,
            action=inferred_request.action,
            target=cleaned_ticket_target,
        )

    if inferred_request.tool_name == "system_status":
        requested_environment = normalized_arguments.get("environment", "").strip()
        if not requested_environment:
            extracted_environment = _extract_environment_argument(question)
            if extracted_environment:
                normalized_arguments["environment"] = extracted_environment
        elif requested_environment:
            normalized_arguments["environment"] = _normalize_environment_value(requested_environment)

    if inferred_request.tool_name == "document_search":
        llm_query = normalized_arguments.pop("query", "").strip()
        if llm_query and inferred_request.target.strip().lower() in {
            "doc",
            "docs",
            "document",
            "documents",
        }:
            inferred_request = InferredToolRequest(
                tool_name=inferred_request.tool_name,
                action=inferred_request.action,
                target=llm_query,
            )
        elif llm_query and not inferred_request.target.strip():
            inferred_request = InferredToolRequest(
                tool_name=inferred_request.tool_name,
                action=inferred_request.action,
                target=llm_query,
            )

        filename = _extract_filename_argument(question)
        if filename and "filename" not in normalized_arguments:
            normalized_arguments["filename"] = filename
        max_results = _extract_search_max_results_argument(question)
        if max_results and "max_results" not in normalized_arguments:
            normalized_arguments["max_results"] = max_results

    return inferred_request, normalized_arguments


def _heuristic_tool_plan(question: str, planning_mode: str = "heuristic_stub") -> ToolPlanResponse:
    inferred_request = infer_tool_request(question)
    inferred_request, arguments = _normalize_planned_request(question, inferred_request, {})
    return _build_tool_plan_response(
        question=question,
        inferred_request=inferred_request,
        arguments=arguments,
        planning_mode=planning_mode,
    )


def _plan_tool_request_with_llm(question: str) -> ToolPlanResponse | None:
    planning_mode, llm_plan = generate_llm_tool_plan(question, SUPPORTED_TOOLS)
    if llm_plan is None:
        return _heuristic_tool_plan(question, planning_mode=planning_mode)

    tool_name = llm_plan["tool_name"].strip().lower()
    metadata = SUPPORTED_TOOLS.get(tool_name)
    if metadata is None:
        return _heuristic_tool_plan(question, planning_mode="heuristic_fallback_invalid_llm_plan")

    action = llm_plan["action"].strip().lower()
    supported_actions = metadata.get("supported_actions", [])
    if action not in supported_actions:
        return _heuristic_tool_plan(question, planning_mode="heuristic_fallback_invalid_llm_plan")

    inferred_request = InferredToolRequest(
        tool_name=tool_name,
        action=action,
        target=llm_plan["target"],
    )
    inferred_request, arguments = _normalize_planned_request(
        question,
        inferred_request,
        llm_plan.get("arguments", {}),
    )
    return _build_tool_plan_response(
        question=question,
        inferred_request=inferred_request,
        arguments=arguments,
        planning_mode=planning_mode,
    )


def plan_tool_request(question: str) -> ToolPlanResponse:
    """Create a structured tool plan from a natural-language tool request."""
    return _plan_tool_request_with_llm(question)

