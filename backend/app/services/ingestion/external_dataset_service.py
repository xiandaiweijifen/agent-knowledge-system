from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

from app.core.config import DATA_ROOT
from app.schemas.domain import IncidentTicket, KnowledgeAsset, ServiceRecord
from app.services.ingestion.document_service import build_utc_timestamp

EXTERNAL_DATA_ROOT = DATA_ROOT / "external"
EXTERNAL_RAW_ROOT = EXTERNAL_DATA_ROOT / "raw"
EXTERNAL_PROCESSED_ROOT = EXTERNAL_DATA_ROOT / "processed"

for path in (EXTERNAL_DATA_ROOT, EXTERNAL_RAW_ROOT, EXTERNAL_PROCESSED_ROOT):
    path.mkdir(parents=True, exist_ok=True)

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)


DATASET_MANIFEST: dict[str, dict[str, Any]] = {
    "bugsrepo_structured": {
        "slug": "bugsrepo_structured",
        "label": "BugsRepo Structured Bug Reports",
        "kind": "ticket_primary",
        "source_url": "https://zenodo.org/records/15003722",
        "expected_formats": ["json", "jsonl", "csv"],
        "recommended_input": "Place the structured bug report export under data/external/raw/bugsrepo_structured/",
        "notes": [
            "Best fit for real incident and ticket metadata.",
            "Good primary source for severity, status, summary, comments, and assignee-like fields.",
        ],
    },
    "customer_support_tickets": {
        "slug": "customer_support_tickets",
        "label": "Customer Support Tickets",
        "kind": "ticket_secondary",
        "source_url": "https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets",
        "expected_formats": ["csv"],
        "recommended_input": "Place the CSV export under data/external/raw/customer_support_tickets/",
        "notes": [
            "Useful for support ticket language, priority, queue, and response drafting patterns.",
            "Good supplement for incident/request/problem phrasing and ticket summaries.",
        ],
    },
    "it_support_v2": {
        "slug": "it_support_v2",
        "label": "IT Support V2 Dialogues",
        "kind": "knowledge_evidence",
        "source_url": "https://huggingface.co/datasets/benjaminmacklin/IT_Support_V2",
        "expected_formats": ["jsonl", "json"],
        "recommended_input": "Place the JSONL export under data/external/raw/it_support_v2/",
        "notes": [
            "Best treated as troubleshooting and support dialogue evidence instead of primary ticket truth data.",
            "Useful for later self-serve troubleshooting and answer style augmentation.",
        ],
    },
    "github_issues_sample": {
        "slug": "github_issues_sample",
        "label": "GitHub Issues Sample",
        "kind": "ticket_secondary",
        "source_url": "https://www.gharchive.org/",
        "expected_formats": ["json", "jsonl", "csv"],
        "recommended_input": "Use a hand-curated or extracted issue sample under data/external/raw/github_issues_sample/",
        "notes": [
            "Useful for modern engineering issue language and lifecycle metadata.",
            "Recommended as a supplement instead of the first large-scale import.",
        ],
    },
    "postmortem_sample": {
        "slug": "postmortem_sample",
        "label": "Incident Postmortem Sample",
        "kind": "knowledge_evidence",
        "source_url": "https://postmortems.app/about",
        "expected_formats": ["json", "jsonl", "csv"],
        "recommended_input": "Use a manually collected postmortem sample under data/external/raw/postmortem_sample/",
        "notes": [
            "Better suited for knowledge evidence than for ticket truth labels.",
            "Good future source for incident summary and evidence retrieval.",
        ],
    },
}

FIELD_ALIASES: dict[str, list[str]] = {
    "external_id": ["bug_id", "id", "issue_id", "ticket_id", "number"],
    "title": ["summary", "title", "subject"],
    "description": ["description", "body", "content"],
    "status": ["status", "state"],
    "severity": ["severity", "priority", "impact"],
    "environment": ["environment", "env"],
    "service": ["service", "service_name", "product", "component", "repo", "repository"],
    "assignee": ["assignee", "owner", "assigned_to"],
    "created_at": ["created_at", "creation_time", "opened_at", "timestamp"],
    "updated_at": ["updated_at", "last_updated", "closed_at", "resolved_at"],
    "comments": ["comments", "discussion", "messages"],
}


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def list_external_dataset_targets() -> list[dict[str, Any]]:
    return [dict(entry) for entry in DATASET_MANIFEST.values()]


def _read_json_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for candidate_key in ("records", "items", "data", "issues", "tickets"):
            candidate = payload.get(candidate_key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return [payload]
    return []


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        payload = json.loads(normalized)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _read_csv_records(path: Path) -> list[dict[str, Any]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                return [dict(row) for row in reader]
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError(f"Unable to read CSV dataset: {path}")


def load_external_dataset_records(input_path: str | Path) -> list[dict[str, Any]]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"External dataset input not found: {path}")

    if path.suffix.lower() == ".json":
        return _read_json_records(path)
    if path.suffix.lower() == ".jsonl":
        return _read_jsonl_records(path)
    if path.suffix.lower() == ".csv":
        return _read_csv_records(path)

    raise ValueError(f"Unsupported dataset format for {path.name}")


def _pick_field(record: dict[str, Any], field_name: str) -> Any:
    for alias in FIELD_ALIASES.get(field_name, []):
        if alias in record and record[alias] not in (None, ""):
            return record[alias]
    return None


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", (value or "").strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "unknown-service"


def _normalize_severity(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"", "--", "---", "n/a", "na", "unspecified", "unknown"}:
        return "unspecified"
    if normalized in {"s1", "s2"}:
        return "high"
    if normalized == "s3":
        return "medium"
    if normalized == "s4":
        return "low"
    if normalized in {"p1", "p0"}:
        return "high"
    if normalized in {"p2", "p3"}:
        return "medium"
    if normalized in {"p4", "p5"}:
        return "low"
    if normalized in {"critical", "blocker", "p0", "sev0", "sev1", "highest"}:
        return "high"
    if normalized in {"major", "p1", "medium", "normal", "moderate"}:
        return "medium"
    if normalized in {"minor", "low", "p2", "p3", "trivial", "lowest"}:
        return "low"
    return normalized


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"closed", "resolved", "done", "completed"}:
        return "closed"
    if normalized in {"new", "open", "assigned", "unconfirmed", "reopened", "in_progress", "in-progress"}:
        return "open"
    if normalized in {"draft", "awaiting_confirmation"}:
        return "draft"
    return normalized or "open"


def _normalize_environment(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"prod", "production"}:
        return "production"
    if normalized in {"stage", "staging"}:
        return "staging"
    if normalized in {"dev", "development"}:
        return "development"
    return normalized or "unspecified"


def _coerce_comment_text(comments: Any) -> str:
    if isinstance(comments, list):
        snippets: list[str] = []
        for item in comments[:3]:
            if isinstance(item, dict):
                candidate = item.get("body") or item.get("text") or item.get("comment")
                if candidate:
                    snippets.append(str(candidate).strip())
            elif item:
                snippets.append(str(item).strip())
        return " | ".join(snippets)
    if comments:
        return str(comments).strip()
    return ""


def _build_service_record(service_name: str) -> ServiceRecord:
    service_id = _slugify(service_name)
    runbook_doc_ids: list[str] = []
    if "payment" in service_id:
        runbook_doc_ids = ["payment_service_runbook.md", "incident_playbook.md"]
    elif "checkout" in service_id:
        runbook_doc_ids = ["checkout_service_runbook.md"]
    elif "workflow" in service_id:
        runbook_doc_ids = ["agent_workflow.md", "workflow_runtime_notes.md"]

    return ServiceRecord(
        service_id=service_id,
        service_name=service_name,
        owner_team="external-dataset-import",
        tier="tier-2",
        environments=["production", "staging", "development"],
        runbook_doc_ids=runbook_doc_ids,
    )


def _build_ticket(
    dataset_slug: str,
    external_id: str,
    *,
    title: str,
    service_id: str,
    environment: str,
    severity: str,
    status: str,
    assignee: str | None,
    created_at: str,
    updated_at: str,
    summary: str,
) -> dict[str, Any]:
    ticket = IncidentTicket(
        ticket_id=f"{dataset_slug.upper()}-{external_id}",
        title=title,
        service=service_id,
        environment=environment,
        severity=severity,
        symptoms=[],
        status=status,
        assignee=assignee,
        created_at=created_at,
        updated_at=updated_at,
        source_run_id=None,
        summary=summary,
    )
    return _model_to_dict(ticket)


def _collect_non_empty_tags(*groups: Any) -> list[str]:
    values: list[str] = []
    for group in groups:
        if isinstance(group, list):
            for item in group:
                if item not in (None, ""):
                    values.append(str(item).strip())
        elif group not in (None, ""):
            values.append(str(group).strip())
    normalized: list[str] = []
    for value in values:
        lowered = value.lower()
        if lowered and lowered not in normalized:
            normalized.append(lowered)
    return normalized


def _build_knowledge_asset(
    dataset_slug: str,
    external_id: str,
    *,
    service_id: str,
    title: str,
    doc_kind: str,
    tags: list[str],
    snippet: str,
) -> dict[str, Any]:
    knowledge_asset = KnowledgeAsset(
        doc_id=f"{dataset_slug}::{external_id}",
        service=service_id,
        doc_kind=doc_kind,
        section_path=[],
        tags=tags,
        source_filename=f"{dataset_slug}_{external_id}.md",
        title=title,
        snippet=snippet.strip() or title,
    )
    return _model_to_dict(knowledge_asset)


def _normalize_bugsrepo_structured_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_tickets: list[dict[str, Any]] = []
    normalized_services: dict[str, dict[str, Any]] = {}
    normalized_knowledge_assets: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        external_id = str(record.get("id") or record.get("bug_id") or record.get("_id") or index)
        title = str(record.get("summary") or f"bugsrepo issue {external_id}").strip()
        product = str(record.get("product") or "").strip()
        component = str(record.get("component") or "").strip()
        service_name = " / ".join(part for part in (product, component) if part) or "unknown-service"
        service_record = _build_service_record(service_name)
        normalized_services[service_record.service_id] = _model_to_dict(service_record)

        created_at = str(record.get("creation_time") or build_utc_timestamp())
        updated_at = str(record.get("last_change_time") or created_at)
        raw_status = str(record.get("status") or "").strip().lower()
        status = "closed" if raw_status in {"resolved", "closed", "verified"} else _normalize_status(raw_status)
        severity = _normalize_severity(record.get("severity") or record.get("priority"))
        summary = " ".join(
            part
            for part in (
                title,
                f"Product: {product}." if product else "",
                f"Component: {component}." if component else "",
                f"Resolution: {record.get('resolution')}." if record.get("resolution") else "",
            )
            if part
        ).strip()

        normalized_tickets.append(
            _build_ticket(
                "bugsrepo_structured",
                external_id,
                title=title,
                service_id=service_record.service_id,
                environment="unspecified",
                severity=severity,
                status=status,
                assignee=str(record.get("assigned_to")).strip() if record.get("assigned_to") else None,
                created_at=created_at,
                updated_at=updated_at,
                summary=summary,
            )
        )

        tags = _collect_non_empty_tags(
            "bugsrepo_structured",
            "external-ticket",
            record.get("type"),
            record.get("classification"),
            record.get("severity"),
            record.get("priority"),
            product,
            component,
        )
        snippet = " ".join(
            part
            for part in (
                title,
                f"Status {record.get('status')}." if record.get("status") else "",
                f"Resolution {record.get('resolution')}." if record.get("resolution") else "",
                f"Comment count {record.get('comment_count')}." if record.get("comment_count") else "",
            )
            if part
        )
        normalized_knowledge_assets.append(
            _build_knowledge_asset(
                "bugsrepo_structured",
                external_id,
                service_id=service_record.service_id,
                title=title,
                doc_kind="issue_report",
                tags=tags,
                snippet=snippet,
            )
        )

    return {
        "ticket_count": len(normalized_tickets),
        "service_count": len(normalized_services),
        "knowledge_asset_count": len(normalized_knowledge_assets),
        "tickets": normalized_tickets,
        "services": list(normalized_services.values()),
        "knowledge_assets": normalized_knowledge_assets,
    }


def _normalize_customer_support_ticket_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_tickets: list[dict[str, Any]] = []
    normalized_services: dict[str, dict[str, Any]] = {}
    normalized_knowledge_assets: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        external_id = str(index)
        title = str(record.get("subject") or f"support ticket {external_id}").strip()
        body = str(record.get("body") or "").strip()
        answer = str(record.get("answer") or "").strip()
        queue = str(record.get("queue") or "support").strip()
        service_name = queue or "support"
        service_record = _build_service_record(service_name)
        normalized_services[service_record.service_id] = _model_to_dict(service_record)

        tag_values = [record.get(f"tag_{position}") for position in range(1, 9)]
        tags = _collect_non_empty_tags(
            "customer_support_tickets",
            "external-ticket",
            record.get("type"),
            queue,
            record.get("language"),
            tag_values,
        )

        normalized_tickets.append(
            _build_ticket(
                "customer_support_tickets",
                external_id,
                title=title,
                service_id=service_record.service_id,
                environment="unspecified",
                severity=_normalize_severity(record.get("priority")),
                status="open",
                assignee=None,
                created_at=build_utc_timestamp(),
                updated_at=build_utc_timestamp(),
                summary=body or title,
            )
        )
        normalized_knowledge_assets.append(
            _build_knowledge_asset(
                "customer_support_tickets",
                external_id,
                service_id=service_record.service_id,
                title=title,
                doc_kind="support_ticket",
                tags=tags,
                snippet=" ".join(part for part in (body, answer) if part),
            )
        )

    return {
        "ticket_count": len(normalized_tickets),
        "service_count": len(normalized_services),
        "knowledge_asset_count": len(normalized_knowledge_assets),
        "tickets": normalized_tickets,
        "services": list(normalized_services.values()),
        "knowledge_assets": normalized_knowledge_assets,
    }


def _extract_dialogue_messages(record: dict[str, Any]) -> tuple[str, str]:
    messages = record.get("messages")
    if not isinstance(messages, list):
        return "", ""

    user_content = ""
    assistant_content = ""
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role == "user" and content and not user_content:
            user_content = content
        if role == "assistant" and content and not assistant_content:
            assistant_content = content
        if user_content and assistant_content:
            break
    return user_content, assistant_content


def _normalize_it_support_v2_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_tickets: list[dict[str, Any]] = []
    normalized_services: dict[str, dict[str, Any]] = {}
    normalized_knowledge_assets: list[dict[str, Any]] = []

    service_record = _build_service_record("it-support")
    normalized_services[service_record.service_id] = _model_to_dict(service_record)

    for index, record in enumerate(records, start=1):
        external_id = str(index)
        user_content, assistant_content = _extract_dialogue_messages(record)
        title = (user_content[:120].strip() if user_content else f"it support dialogue {external_id}").strip()

        normalized_tickets.append(
            _build_ticket(
                "it_support_v2",
                external_id,
                title=title,
                service_id=service_record.service_id,
                environment="unspecified",
                severity="unspecified",
                status="open",
                assignee=None,
                created_at=build_utc_timestamp(),
                updated_at=build_utc_timestamp(),
                summary=user_content or title,
            )
        )
        normalized_knowledge_assets.append(
            _build_knowledge_asset(
                "it_support_v2",
                external_id,
                service_id=service_record.service_id,
                title=title,
                doc_kind="support_resolution",
                tags=["it_support_v2", "support-dialogue", "external-knowledge"],
                snippet=" ".join(part for part in (user_content, assistant_content) if part),
            )
        )

    return {
        "ticket_count": len(normalized_tickets),
        "service_count": len(normalized_services),
        "knowledge_asset_count": len(normalized_knowledge_assets),
        "tickets": normalized_tickets,
        "services": list(normalized_services.values()),
        "knowledge_assets": normalized_knowledge_assets,
    }


def _normalize_generic_records(dataset_slug: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_tickets: list[dict[str, Any]] = []
    normalized_services: dict[str, dict[str, Any]] = {}
    normalized_knowledge_assets: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        external_id = str(_pick_field(record, "external_id") or index)
        title = str(_pick_field(record, "title") or f"{dataset_slug} issue {external_id}").strip()
        description = str(_pick_field(record, "description") or "").strip()
        service_name = str(_pick_field(record, "service") or "unknown-service").strip()
        assignee = _pick_field(record, "assignee")
        created_at = str(_pick_field(record, "created_at") or build_utc_timestamp())
        updated_at = str(_pick_field(record, "updated_at") or created_at)
        comments_text = _coerce_comment_text(_pick_field(record, "comments"))
        severity = _normalize_severity(_pick_field(record, "severity"))
        status = _normalize_status(_pick_field(record, "status"))
        environment = _normalize_environment(_pick_field(record, "environment"))

        service_record = _build_service_record(service_name)
        normalized_services[service_record.service_id] = _model_to_dict(service_record)

        normalized_tickets.append(
            _build_ticket(
                dataset_slug,
                external_id,
                title=title,
                service_id=service_record.service_id,
                environment=environment,
                severity=severity,
                status=status,
                assignee=str(assignee).strip() if assignee else None,
                created_at=created_at,
                updated_at=updated_at,
                summary=description or title,
            )
        )

        asset_snippet_parts = [part for part in (description, comments_text) if part]
        normalized_knowledge_assets.append(
            _build_knowledge_asset(
                dataset_slug,
                external_id,
                service_id=service_record.service_id,
                title=title,
                doc_kind="issue_report",
                tags=[dataset_slug, "external-ticket", status, severity],
                snippet=" ".join(asset_snippet_parts[:2]).strip() or title,
            )
        )

    return {
        "ticket_count": len(normalized_tickets),
        "service_count": len(normalized_services),
        "knowledge_asset_count": len(normalized_knowledge_assets),
        "tickets": normalized_tickets,
        "services": list(normalized_services.values()),
        "knowledge_assets": normalized_knowledge_assets,
    }


def normalize_ticket_dataset_records(
    dataset_slug: str,
    records: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    if dataset_slug not in DATASET_MANIFEST:
        raise ValueError(f"Unknown dataset slug: {dataset_slug}")

    selected_records = records[:limit] if limit and limit > 0 else records
    if dataset_slug == "bugsrepo_structured":
        normalized_bundle = _normalize_bugsrepo_structured_records(selected_records)
    elif dataset_slug == "customer_support_tickets":
        normalized_bundle = _normalize_customer_support_ticket_records(selected_records)
    elif dataset_slug == "it_support_v2":
        normalized_bundle = _normalize_it_support_v2_records(selected_records)
    else:
        normalized_bundle = _normalize_generic_records(dataset_slug, selected_records)

    return {
        "dataset": DATASET_MANIFEST[dataset_slug],
        "record_count": len(selected_records),
        "ticket_count": normalized_bundle["ticket_count"],
        "service_count": normalized_bundle["service_count"],
        "knowledge_asset_count": normalized_bundle["knowledge_asset_count"],
        "tickets": normalized_bundle["tickets"],
        "services": normalized_bundle["services"],
        "knowledge_assets": normalized_bundle["knowledge_assets"],
    }


def write_normalized_external_dataset(
    dataset_slug: str,
    normalized_bundle: dict[str, Any],
) -> Path:
    output_path = EXTERNAL_PROCESSED_ROOT / f"{dataset_slug}.normalized.json"
    output_path.write_text(
        json.dumps(normalized_bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
