"""Shared constants, regex patterns, and utility functions used by tool adapters and planning."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.core.config import DATA_ROOT, settings
from app.schemas.domain import IncidentTicket, ServiceRecord, StatusSnapshot
from app.services.ingestion.document_service import build_utc_timestamp


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

ACTION_PATTERN = re.compile(
    r"\b(create|open|close|draft|submit|prepare|deploy|restart|rollback|run|execute|trigger|query|update|delete|search|find|check|show|inspect|lookup|list|set|move)\b",
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
SERVICE_DEPENDENCIES_FOR_PATTERN = re.compile(
    r"^(service\s+dependencies|dependencies|dependency\s+map|dependency\s+health)\s+for\s+",
    re.IGNORECASE,
)
FILENAME_PATTERN = re.compile(
    r"\b([A-Za-z0-9._-]+\.(?:txt|md|json|pdf|docx))\b",
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

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

TICKET_DATA_DIR = DATA_ROOT / "tool_state"
TICKET_DATA_DIR.mkdir(parents=True, exist_ok=True)
TICKET_STORE_PATH = TICKET_DATA_DIR / "tickets.json"
MOCK_SERVICE_PATH = DATA_ROOT / "mock_services.json"
MOCK_STATUS_SNAPSHOTS_PATH = DATA_ROOT / "mock_status_snapshots.json"
ENGINEERING_DEPENDENCY_MAP_PATH = DATA_ROOT / "raw" / "engineering_dependency_map.json"
TOOL_OUTPUT_SCHEMA_VERSION = "tool-output-v1"


# ---------------------------------------------------------------------------
# Generic output helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_json_payload(path: Path, default: Any) -> Any:
    if not path.exists() or not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _load_mock_services() -> list[dict[str, Any]]:
    payload = _load_json_payload(MOCK_SERVICE_PATH, default=[])
    return payload if isinstance(payload, list) else []


def _load_mock_status_snapshots() -> list[dict[str, Any]]:
    payload = _load_json_payload(MOCK_STATUS_SNAPSHOTS_PATH, default=[])
    return payload if isinstance(payload, list) else []


def _load_engineering_dependency_map() -> list[dict[str, Any]]:
    payload = _load_json_payload(ENGINEERING_DEPENDENCY_MAP_PATH, default={})
    if not isinstance(payload, dict):
        return []
    dependencies = payload.get("dependencies", [])
    return dependencies if isinstance(dependencies, list) else []


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def _normalize_environment_value(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "dev":
        return "development"
    return normalized


def _normalize_status_scenario_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-")


def _normalize_dependency_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-")


def _normalize_failure_signal(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized)
    normalized = re.sub(r"_{2,}", "_", normalized)
    return normalized.strip("_")


def _canonicalize_service_id(target: str) -> str:
    normalized = unicodedata.normalize("NFKC", target).strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-") or "service"


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


# ---------------------------------------------------------------------------
# Argument extractors
# ---------------------------------------------------------------------------

def _extract_filename_argument(question: str) -> str | None:
    match = FILENAME_PATTERN.search(question)
    return match.group(1) if match else None


def _extract_ticket_id_argument(question: str) -> str | None:
    match = TICKET_ID_PATTERN.search(question)
    return match.group(1).upper() if match else None


def _extract_environment_argument(question: str) -> str | None:
    match = ENVIRONMENT_ARGUMENT_PATTERN.search(question)
    if not match:
        return None
    for group in match.groups():
        if group:
            return _normalize_environment_value(group)
    return None


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


def _extract_ticket_target_filter(question: str) -> str | None:
    match = TICKET_LIST_TARGET_PATTERN.search(question.strip())
    if not match:
        return None
    target = ENVIRONMENT_SEGMENT_PATTERN.sub("", match.group("target")).strip(" .")
    target = RESULT_LIMIT_PATTERN.sub("", target).strip(" .")
    target = re.sub(r"\band\s+show\b", "", target, flags=re.IGNORECASE).strip(" .")
    return _canonicalize_ticket_target(target)


def _extract_search_max_results_argument(question: str) -> str | None:
    match = RESULT_LIMIT_PATTERN.search(question)
    if not match:
        return None
    for group in match.groups():
        if group:
            return group
    return None


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


# ---------------------------------------------------------------------------
# Ticket target helpers (used by planning and ticketing adapter)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Domain model builders (service record, status snapshot)
# ---------------------------------------------------------------------------

def _build_service_record(target: str) -> ServiceRecord:
    service_id = _canonicalize_service_id(target)
    mock_services = _load_mock_services()
    for record in mock_services:
        candidate_id = _canonicalize_service_id(str(record.get("service_id") or record.get("service_name") or ""))
        if candidate_id != service_id:
            continue
        return ServiceRecord(
            service_id=candidate_id,
            service_name=str(record.get("service_name") or target.strip() or candidate_id),
            owner_team=str(record.get("owner_team") or "platform-operations"),
            tier=str(record.get("tier") or "tier-2"),
            environments=[
                _normalize_environment_value(str(item))
                for item in record.get("environments", [])
                if str(item).strip()
            ],
            runbook_doc_ids=[str(item) for item in record.get("runbook_doc_ids", []) if str(item).strip()],
        )

    runbook_doc_ids: list[str] = []
    if "payment" in service_id:
        runbook_doc_ids = ["payment_service_runbook.md"]
    elif "checkout" in service_id:
        runbook_doc_ids = ["checkout_service_runbook.md"]
    elif "workflow" in service_id:
        runbook_doc_ids = ["agent_workflow.md", "workflow_runtime_notes.md"]

    return ServiceRecord(
        service_id=service_id,
        service_name=target.strip() or service_id,
        owner_team="platform-operations",
        tier="tier-1" if "payment" in service_id else "tier-2",
        environments=["production", "staging", "development"],
        runbook_doc_ids=runbook_doc_ids,
    )


def _build_status_snapshot(
    service_record: ServiceRecord,
    environment: str,
    scenario: str = "",
) -> StatusSnapshot:
    normalized_environment = _normalize_environment_value(environment or settings.app_env or "development")
    normalized_scenario = _normalize_status_scenario_value(scenario)
    matching_snapshots: list[dict[str, Any]] = []
    for snapshot in _load_mock_status_snapshots():
        snapshot_service = _canonicalize_service_id(
            str(snapshot.get("service") or snapshot.get("service_id") or "")
        )
        snapshot_environment = _normalize_environment_value(str(snapshot.get("environment") or ""))
        if snapshot_service != service_record.service_id or snapshot_environment != normalized_environment:
            continue
        matching_snapshots.append(snapshot)

    selected_snapshot: dict[str, Any] | None = None
    if normalized_scenario:
        for snapshot in matching_snapshots:
            snapshot_scenario = _normalize_status_scenario_value(str(snapshot.get("scenario_id") or ""))
            if snapshot_scenario == normalized_scenario:
                selected_snapshot = snapshot
                break

    if selected_snapshot is None and matching_snapshots:
        for snapshot in matching_snapshots:
            if bool(snapshot.get("is_default")):
                selected_snapshot = snapshot
                break
        if selected_snapshot is None:
            selected_snapshot = matching_snapshots[0]

    if selected_snapshot is not None:
        return StatusSnapshot(
            service=service_record.service_id,
            environment=normalized_environment,
            health=str(selected_snapshot.get("health") or "unknown"),
            scenario_id=(
                _normalize_status_scenario_value(str(selected_snapshot.get("scenario_id") or ""))
                or None
            ),
            latency_p95_ms=(
                int(selected_snapshot["latency_p95_ms"])
                if selected_snapshot.get("latency_p95_ms") is not None
                else None
            ),
            error_rate=float(selected_snapshot["error_rate"]) if selected_snapshot.get("error_rate") is not None else None,
            cpu_percent=float(selected_snapshot["cpu_percent"]) if selected_snapshot.get("cpu_percent") is not None else None,
            memory_percent=float(selected_snapshot["memory_percent"]) if selected_snapshot.get("memory_percent") is not None else None,
            active_alerts=[str(item) for item in selected_snapshot.get("active_alerts", []) if str(item).strip()],
            updated_at=str(selected_snapshot.get("updated_at") or build_utc_timestamp()),
            summary=str(selected_snapshot.get("summary") or ""),
        )

    healthy = normalized_environment != "production"
    return StatusSnapshot(
        service=service_record.service_id,
        environment=normalized_environment,
        health="healthy" if healthy else "degraded",
        scenario_id="fallback_healthy" if healthy else "fallback_degraded",
        latency_p95_ms=145 if healthy else 220,
        error_rate=0.002 if healthy else 0.008,
        cpu_percent=41.0 if healthy else 56.0,
        memory_percent=48.0 if healthy else 62.0,
        active_alerts=[] if healthy else ["latency_elevated"],
        updated_at=build_utc_timestamp(),
        summary=(
            f"{service_record.service_name} is {'healthy' if healthy else 'degraded'} "
            f"in {normalized_environment}."
        ),
    )


# ---------------------------------------------------------------------------
# Ticket record normalizer (used by JsonListRepository callbacks)
# ---------------------------------------------------------------------------

def _normalize_ticket_record(ticket: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(ticket)
    ticket_id = normalized.get("ticket_id", "").strip()
    target = _canonicalize_ticket_target(normalized.get("target", "").strip() or "ticket")
    environment = normalized.get("environment", "unspecified")
    severity = normalized.get("severity", "unspecified")
    service = normalized.get("service", "").strip() or _canonicalize_service_id(target)
    normalized["target"] = target
    normalized["service"] = service
    normalized["title"] = normalized.get("title", "").strip() or (
        f"{severity.title()} severity incident for {service} in {environment}"
    )
    normalized["summary"] = (
        normalized.get("summary", "").strip()
        or normalized.get("supporting_summary", "").strip()
    )
    normalized.update(
        _build_tool_output_metadata(
            output_kind="record",
            resource_type="ticket",
            target=target,
            resource_id=ticket_id or None,
        )
    )
    normalized["ticket_record"] = IncidentTicket(
        ticket_id=ticket_id,
        title=normalized["title"],
        service=service,
        environment=environment,
        severity=severity,
        symptoms=[],
        status=normalized.get("status", "open"),
        assignee=normalized.get("assignee"),
        created_at=normalized.get("created_at", ""),
        updated_at=normalized.get("updated_at", normalized.get("created_at", "")),
        source_run_id=normalized.get("source_run_id"),
        summary=normalized["summary"],
    ).model_dump(mode="json")
    return normalized


# ---------------------------------------------------------------------------
# Document search scoring helpers
# ---------------------------------------------------------------------------

def _infer_doc_kind(filename: str) -> str:
    stem = Path(filename).stem.lower()
    if "runbook" in stem:
        return "runbook"
    if "incident" in stem or "postmortem" in stem:
        return "incident_postmortem"
    if "faq" in stem:
        return "faq"
    if "deploy" in stem or "release" in stem:
        return "deployment"
    if "workflow" in stem:
        return "workflow"
    return "reference"


def _tokenize_search_terms(query: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", query.lower()) if token]


def _normalize_search_excerpt(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("�", " ")
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

    if cleaned and cleaned[0].isalnum() and not cleaned.startswith(("RAG", "Retrieval", "Reranking")):
        first_space = cleaned.find(" ")
        if 0 < first_space < 24:
            candidate = cleaned[first_space + 1:].strip()
            if candidate and candidate[0].isupper():
                cleaned = candidate

    return cleaned


def _extract_search_snippet(content: str, first_index: int, query: str) -> str:
    snippet_start = max(0, first_index - 120)
    snippet_end = min(len(content), first_index + len(query) + 180)

    local_start = first_index
    for index in range(first_index, snippet_start, -1):
        if content[index - 1] in ".!?\n":
            local_start = index
            break

    local_end = snippet_end
    for index in range(first_index + len(query), snippet_end):
        if content[index] in ".!?\n":
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
