from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.agent import tool_service
from app.services.agent.state_store import JsonListRepository
from app.services.ingestion.document_service import build_utc_timestamp


def load_normalized_external_bundle(input_path: str | Path) -> dict[str, Any]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Normalized external dataset bundle not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("normalized_external_bundle_must_be_object")

    tickets = payload.get("tickets")
    if not isinstance(tickets, list):
        raise ValueError("normalized_external_bundle_missing_tickets")

    return payload


def _ticket_store_repository() -> JsonListRepository:
    return JsonListRepository(
        tool_service.TICKET_STORE_PATH,
        normalizer=tool_service._normalize_ticket_record,
    )


def _convert_import_ticket(record: dict[str, Any], dataset_slug: str) -> dict[str, Any]:
    service = str(record.get("service") or "unknown-service").strip()
    title = str(record.get("title") or f"Imported incident for {service}").strip()
    summary = str(record.get("summary") or title).strip()
    created_at = str(record.get("created_at") or build_utc_timestamp())
    updated_at = str(record.get("updated_at") or created_at)

    return {
        "ticket_id": str(record.get("ticket_id") or "").strip(),
        "target": service,
        "service": service,
        "status": str(record.get("status") or "open").strip().lower(),
        "severity": str(record.get("severity") or "unspecified").strip().lower(),
        "environment": str(record.get("environment") or "unspecified").strip().lower(),
        "created_at": created_at,
        "updated_at": updated_at,
        "title": title,
        "summary": summary,
        "assignee": record.get("assignee"),
        "source_run_id": record.get("source_run_id"),
        "import_source": dataset_slug,
        "imported_at": build_utc_timestamp(),
    }


def import_normalized_tickets_to_store(
    input_path: str | Path,
    *,
    limit: int | None = None,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    bundle = load_normalized_external_bundle(input_path)
    dataset = bundle.get("dataset", {})
    dataset_slug = str(dataset.get("slug") or "external_dataset").strip() or "external_dataset"

    raw_tickets = bundle.get("tickets", [])
    selected_tickets = raw_tickets[:limit] if limit and limit > 0 else raw_tickets

    repository = _ticket_store_repository()
    existing_records = repository.load()
    existing_by_id = {
        str(record.get("ticket_id") or "").strip(): record
        for record in existing_records
        if str(record.get("ticket_id") or "").strip()
    }

    imported_count = 0
    skipped_count = 0
    updated_count = 0

    for ticket in selected_tickets:
        imported_record = _convert_import_ticket(ticket, dataset_slug)
        ticket_id = imported_record["ticket_id"]
        if not ticket_id:
            skipped_count += 1
            continue

        if ticket_id in existing_by_id:
            if not overwrite_existing:
                skipped_count += 1
                continue
            existing_by_id[ticket_id] = imported_record
            updated_count += 1
            continue

        existing_by_id[ticket_id] = imported_record
        imported_count += 1

    merged_records = sorted(
        existing_by_id.values(),
        key=lambda record: (record.get("updated_at", ""), record.get("ticket_id", "")),
    )
    repository.save(merged_records)

    return {
        "dataset": dataset_slug,
        "input_path": str(Path(input_path).resolve()),
        "selected_ticket_count": len(selected_tickets),
        "imported_count": imported_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "ticket_store_path": str(tool_service.TICKET_STORE_PATH),
        "ticket_store_count": len(merged_records),
        "overwrite_existing": overwrite_existing,
    }
