"""Ticketing tool adapter — create, draft, submit, update, close, query, and list tickets."""

import json
import re
import uuid
from typing import Any

from app.schemas.domain import IncidentTicket
from app.schemas.tools import ToolExecutionRequest, ToolExecutionResponse
from app.services.agent.state_store import JsonListRepository
from app.services.ingestion.document_service import build_utc_timestamp

from app.services.agent.adapters._shared import (
    TICKET_STORE_PATH,
    _build_tool_output_metadata,
    _canonicalize_service_id,
    _canonicalize_ticket_target,
    _normalize_ticket_record,
    _parse_max_results_argument,
)
from app.services.agent.adapters.registry import register_adapter


# ---------------------------------------------------------------------------
# Ticket store I/O
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Ticket artifact helpers
# ---------------------------------------------------------------------------

def _ticket_artifact_dir():
    return TICKET_STORE_PATH.parent / "tickets"


def _ticket_artifact_paths(ticket_id: str):
    safe_ticket_id = re.sub(r"[^A-Za-z0-9._-]+", "-", ticket_id.strip()) or "ticket"
    ticket_dir = _ticket_artifact_dir()
    return ticket_dir / f"{safe_ticket_id}.md", ticket_dir / f"{safe_ticket_id}.json"


def _format_optional_ticket_value(ticket: dict[str, Any], key: str, default: str = "unspecified") -> str:
    value = ticket.get(key)
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _render_ticket_markdown(ticket: dict[str, Any]) -> str:
    ticket_id = _format_optional_ticket_value(ticket, "ticket_id", "TICKET-UNKNOWN")
    summary = _format_optional_ticket_value(ticket, "summary", "No summary provided.")
    supporting_summary = _format_optional_ticket_value(ticket, "supporting_summary", "")
    submitted_at = _format_optional_ticket_value(ticket, "submitted_at", "")
    closed_at = _format_optional_ticket_value(ticket, "closed_at", "")

    lifecycle_lines = [
        f"- Created At: {_format_optional_ticket_value(ticket, 'created_at')}",
        f"- Updated At: {_format_optional_ticket_value(ticket, 'updated_at')}",
    ]
    if submitted_at:
        lifecycle_lines.append(f"- Submitted At: {submitted_at}")
    if closed_at:
        lifecycle_lines.append(f"- Closed At: {closed_at}")

    sections = [
        f"# {ticket_id}",
        "",
        f"- Title: {_format_optional_ticket_value(ticket, 'title', 'Untitled incident')}",
        f"- Service: {_format_optional_ticket_value(ticket, 'service')}",
        f"- Target: {_format_optional_ticket_value(ticket, 'target')}",
        f"- Environment: {_format_optional_ticket_value(ticket, 'environment')}",
        f"- Severity: {_format_optional_ticket_value(ticket, 'severity')}",
        f"- Status: {_format_optional_ticket_value(ticket, 'status')}",
        f"- Submission State: {_format_optional_ticket_value(ticket, 'submission_state')}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Lifecycle",
        "",
        *lifecycle_lines,
    ]
    if supporting_summary and supporting_summary != summary:
        sections.extend(["", "## Supporting Evidence", "", supporting_summary])
    return "\n".join(sections).rstrip() + "\n"


def _persist_ticket_artifacts(ticket: dict[str, Any]) -> dict[str, Any]:
    ticket_id = str(ticket.get("ticket_id") or "").strip()
    if not ticket_id:
        return ticket

    markdown_path, json_path = _ticket_artifact_paths(ticket_id)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    ticket["ticket_artifact_path"] = str(markdown_path)
    ticket["ticket_artifact_json_path"] = str(json_path)
    markdown_path.write_text(_render_ticket_markdown(ticket), encoding="utf-8")
    json_path.write_text(json.dumps(ticket, ensure_ascii=False, indent=2), encoding="utf-8")
    return ticket


# ---------------------------------------------------------------------------
# Ticket record builders
# ---------------------------------------------------------------------------

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
        summary_parts.append(f"Search for '{query}' matched {matched_count} supporting document(s).")
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
        status_sentence = f"System status snapshot for {status_subject} reported status {supporting_status}"
        if supporting_status_app_env:
            status_sentence += f" in {supporting_status_app_env}"
        if supporting_status_requested_env:
            status_sentence += f" for requested {supporting_status_requested_env}"
        summary_parts.append(f"{status_sentence}.")

    return " ".join(summary_parts).strip()


def _next_ticket_id(tickets: list[dict[str, Any]]) -> str:
    max_id = 0
    for ticket in tickets:
        raw_ticket_id = str(ticket.get("ticket_id", "")).strip().upper()
        match = re.match(r"^TICKET-(\d+)$", raw_ticket_id)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"TICKET-{max_id + 1:04d}"


def _build_incident_ticket_record(
    *,
    ticket_id: str,
    title: str,
    service: str,
    environment: str,
    severity: str,
    status: str,
    created_at: str,
    updated_at: str,
    summary: str,
    assignee: str | None = None,
    source_run_id: str | None = None,
    symptoms: list[str] | None = None,
) -> dict[str, Any]:
    return IncidentTicket(
        ticket_id=ticket_id,
        title=title,
        service=service,
        environment=environment,
        severity=severity,
        symptoms=symptoms or [],
        status=status,
        assignee=assignee,
        created_at=created_at,
        updated_at=updated_at,
        source_run_id=source_run_id,
        summary=summary,
    ).model_dump(mode="json")


def _build_ticket_collection_records(tickets: list[dict[str, Any]]) -> list[dict[str, str]]:
    serialized_records: list[dict[str, str]] = []
    for ticket in tickets:
        serialized_records.append(
            {
                "ticket_id": ticket.get("ticket_id", ""),
                "title": ticket.get("title", ""),
                "service": ticket.get("service", ticket.get("target", "")),
                "target": ticket.get("target", ""),
                "status": ticket.get("status", ""),
                "severity": ticket.get("severity", ""),
                "environment": ticket.get("environment", ""),
                "summary": ticket.get("summary", ticket.get("supporting_summary", "")),
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


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

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
        ticket_id = _next_ticket_id(tickets)
        service = _canonicalize_service_id(target)
        environment = request.arguments.get("environment", "unspecified")
        severity = request.arguments.get("severity", "unspecified")
        summary = (
            request.arguments.get("supporting_summary", "").strip()
            or _build_supporting_summary(request.arguments)
        )
        title = f"{severity.title()} severity incident for {service} in {environment}"
        ticket = {
            **_build_tool_output_metadata(
                output_kind="record",
                resource_type="ticket",
                target=target,
                resource_id=ticket_id,
            ),
            "ticket_id": ticket_id,
            "title": title,
            "service": service,
            "target": target,
            "status": "open",
            "severity": severity,
            "environment": environment,
            "created_at": now,
            "updated_at": now,
            "summary": summary,
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
        if summary:
            ticket["supporting_summary"] = summary
        ticket["ticket_record"] = _build_incident_ticket_record(
            ticket_id=ticket_id,
            title=title,
            service=service,
            environment=environment,
            severity=severity,
            status="open",
            created_at=now,
            updated_at=now,
            summary=summary,
            symptoms=[request.arguments.get("supporting_status", "").strip()]
            if request.arguments.get("supporting_status", "").strip()
            else [],
        )
        _persist_ticket_artifacts(ticket)
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

    if action == "draft":
        ticket_id = _next_ticket_id(tickets)
        service = _canonicalize_service_id(target)
        environment = request.arguments.get("environment", "unspecified")
        severity = request.arguments.get("severity", "unspecified")
        summary = (
            request.arguments.get("supporting_summary", "").strip()
            or _build_supporting_summary(request.arguments)
        )
        title = request.arguments.get(
            "title",
            f"{severity.title()} severity incident for {service} in {environment}",
        )
        ticket = {
            **_build_tool_output_metadata(
                output_kind="record",
                resource_type="ticket",
                target=target,
                resource_id=ticket_id,
            ),
            "ticket_id": ticket_id,
            "title": title,
            "service": service,
            "target": target,
            "status": "draft",
            "submission_state": "awaiting_user_confirmation",
            "severity": severity,
            "environment": environment,
            "created_at": now,
            "updated_at": now,
            "summary": summary,
            "draft_created_at": now,
        }
        if summary:
            ticket["supporting_summary"] = summary
        ticket["ticket_record"] = _build_incident_ticket_record(
            ticket_id=ticket_id,
            title=title,
            service=service,
            environment=environment,
            severity=severity,
            status="draft",
            created_at=now,
            updated_at=now,
            summary=summary,
        )
        _persist_ticket_artifacts(ticket)
        tickets.append(ticket)
        _save_ticket_store(tickets)

        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Prepared ticket draft {ticket_id} for {target}.",
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
        ticket.setdefault(
            "ticket_record",
            IncidentTicket(
                ticket_id=ticket.get("ticket_id", ""),
                title=ticket.get("title", f"Incident for {ticket.get('target', '')}"),
                service=ticket.get("service", _canonicalize_service_id(ticket.get("target", ""))),
                environment=ticket.get("environment", "unspecified"),
                severity=ticket.get("severity", "unspecified"),
                symptoms=[],
                status=ticket.get("status", "open"),
                assignee=ticket.get("assignee"),
                created_at=ticket.get("created_at", now),
                updated_at=ticket.get("updated_at", now),
                source_run_id=ticket.get("source_run_id"),
                summary=ticket.get("summary", ticket.get("supporting_summary", "")),
            ).model_dump(mode="json"),
        )
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

    if action == "submit":
        current_status = str(ticket.get("status", "")).strip().lower()
        if current_status not in {"draft", "awaiting_confirmation"}:
            return ToolExecutionResponse(
                tool_name="ticketing",
                action=action,
                target=target,
                execution_status="invalid_state",
                execution_mode="local_adapter",
                result_summary=(
                    f"Ticket {ticket.get('ticket_id', '')} is not in a submittable draft state."
                ),
                trace_id=trace_id,
                executed_at=now,
                output=ticket,
            )

        ticket["status"] = "open"
        ticket["submission_state"] = "submitted"
        ticket["submitted_at"] = now
        ticket["updated_at"] = now
        ticket.setdefault("service", _canonicalize_service_id(ticket.get("target", "")))
        ticket.setdefault("title", f"Incident for {ticket.get('target', '')}")
        ticket["ticket_record"] = _build_incident_ticket_record(
            ticket_id=ticket.get("ticket_id", ""),
            title=ticket.get("title", ""),
            service=ticket.get("service", ""),
            environment=ticket.get("environment", "unspecified"),
            severity=ticket.get("severity", "unspecified"),
            status="open",
            created_at=ticket.get("created_at", now),
            updated_at=now,
            summary=ticket.get("summary", ticket.get("supporting_summary", "")),
            assignee=ticket.get("assignee"),
            source_run_id=ticket.get("source_run_id"),
        )
        _persist_ticket_artifacts(ticket)
        _save_ticket_store(tickets)

        return ToolExecutionResponse(
            tool_name="ticketing",
            action=action,
            target=target,
            execution_status="completed",
            execution_mode="local_adapter",
            result_summary=f"Submitted ticket draft {ticket['ticket_id']} for {target}.",
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
            ticket["summary"] = supporting_summary
        normalized_status = request.arguments.get("status", "").strip().lower()
        if normalized_status == "open":
            ticket.pop("closed_at", None)
        elif normalized_status == "closed":
            ticket["closed_at"] = now
        ticket["updated_at"] = now
        ticket.setdefault("service", _canonicalize_service_id(ticket.get("target", "")))
        ticket.setdefault("title", f"Incident for {ticket.get('target', '')}")
        ticket["ticket_record"] = _build_incident_ticket_record(
            ticket_id=ticket.get("ticket_id", ""),
            title=ticket.get("title", ""),
            service=ticket.get("service", ""),
            environment=ticket.get("environment", "unspecified"),
            severity=ticket.get("severity", "unspecified"),
            status=ticket.get("status", "open"),
            created_at=ticket.get("created_at", now),
            updated_at=now,
            summary=ticket.get("summary", ticket.get("supporting_summary", "")),
            assignee=ticket.get("assignee"),
            source_run_id=ticket.get("source_run_id"),
        )
        _persist_ticket_artifacts(ticket)
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
            ticket["summary"] = supporting_summary
        ticket["status"] = "closed"
        ticket["updated_at"] = now
        ticket["closed_at"] = now
        ticket.setdefault("service", _canonicalize_service_id(ticket.get("target", "")))
        ticket.setdefault("title", f"Incident for {ticket.get('target', '')}")
        ticket["ticket_record"] = _build_incident_ticket_record(
            ticket_id=ticket.get("ticket_id", ""),
            title=ticket.get("title", ""),
            service=ticket.get("service", ""),
            environment=ticket.get("environment", "unspecified"),
            severity=ticket.get("severity", "unspecified"),
            status="closed",
            created_at=ticket.get("created_at", now),
            updated_at=now,
            summary=ticket.get("summary", ticket.get("supporting_summary", "")),
            assignee=ticket.get("assignee"),
            source_run_id=ticket.get("source_run_id"),
        )
        _persist_ticket_artifacts(ticket)
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


register_adapter("ticketing", _run_ticketing_tool)
