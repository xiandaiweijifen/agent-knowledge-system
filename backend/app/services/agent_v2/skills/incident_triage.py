from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.agent_v2.state import AgentState


INCIDENT_TRIAGE_PLANNING_MODE = "agent_v2_incident_triage"
EXTERNAL_EVIDENCE_PREFIXES = "customer_support_tickets_,it_support_v2_,bugsrepo_structured_"


ExecuteStep = Callable[..., tuple[dict[str, Any], Any]]


def build_incident_triage_summary(
    *,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict[str, Any],
    search_output: dict[str, Any] | None,
    draft_output: dict[str, Any] | None,
) -> str:
    status_summary = status_output.get("summary") or f"{service} status checked in {environment}."
    if draft_output is None:
        return (
            f"Incident triage for {service} in {environment} found no ticket-worthy issue. "
            f"{status_summary}"
        )

    matched_documents = ""
    if isinstance(search_output, dict):
        matched_documents = str(search_output.get("matched_documents") or "").strip()
    document_clause = f" Supporting evidence came from {matched_documents}." if matched_documents else ""
    return (
        f"Incident triage for {service} in {environment} found a likely {symptom} issue. "
        f"{status_summary} Prepared ticket draft {draft_output.get('ticket_id', 'unknown')} for operator review."
        f"{document_clause}"
    )


def build_external_evidence_query(
    *,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict[str, Any],
) -> str:
    alerts = status_output.get("active_alerts")
    alert_text = " ".join(str(item) for item in alerts if str(item).strip()) if isinstance(alerts, list) else ""
    status_summary = str(status_output.get("summary") or "")
    return " ".join(
        part
        for part in [service, environment, symptom, alert_text, status_summary]
        if part.strip()
    ).strip()


def build_ticket_submission_confirmation(
    *,
    service: str,
    environment: str,
    draft_output: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    ticket_id = str(draft_output.get("ticket_id") or "unknown").strip()
    confirmation_question = (
        f"Draft {ticket_id} is ready for {service} in {environment}. Do you want me to submit it?"
    )
    return confirmation_question, {
        "question": confirmation_question,
        "planning_mode": INCIDENT_TRIAGE_PLANNING_MODE,
        "confirmation_kind": "ticket_submission",
        "missing_fields": ["submission_confirmation"],
        "follow_up_questions": [
            f"Confirm whether to submit ticket draft {ticket_id}."
        ],
        "clarification_summary": confirmation_question,
        "ticket_id": ticket_id,
        "service": service,
        "environment": environment,
    }


def select_evidence_filename(service_record: dict[str, Any], symptom: str) -> str | None:
    runbook_doc_ids = service_record.get("runbook_doc_ids")
    if not isinstance(runbook_doc_ids, list) or not runbook_doc_ids:
        return None

    lowered_symptom = symptom.lower()
    preferred_keywords = [lowered_symptom]
    if lowered_symptom == "timeout":
        preferred_keywords.extend(["runbook", "incident", "payment"])

    for keyword in preferred_keywords:
        for candidate in runbook_doc_ids:
            if isinstance(candidate, str) and keyword in candidate.lower():
                return candidate

    first_candidate = runbook_doc_ids[0]
    return first_candidate if isinstance(first_candidate, str) and first_candidate.strip() else None


def run_review_service_health_skill(
    *,
    state: AgentState,
    question: str,
    service: str,
    environment: str,
    symptom: str,
    planning_mode: str = INCIDENT_TRIAGE_PLANNING_MODE,
    execute_step: ExecuteStep,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status_step, status_execution = execute_step(
        state=state,
        step_index=1,
        question=question,
        tool_name="system_status",
        action="query",
        target=service,
        arguments={"environment": environment, "issue_type": symptom},
        planning_mode=planning_mode,
    )
    return [status_step], status_execution.model_dump().get("output", {})


def run_collect_incident_evidence_skill(
    *,
    state: AgentState,
    question: str,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict[str, Any],
    execute_step: ExecuteStep,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    evidence_filename = select_evidence_filename(
        status_output.get("service_record", {}),
        symptom,
    )
    search_step, search_execution = execute_step(
        state=state,
        step_index=2,
        question=question,
        tool_name="document_search",
        action="query",
        target=symptom,
        arguments={
            "max_results": "3",
            **({"filename": evidence_filename} if evidence_filename else {}),
        },
        planning_mode=INCIDENT_TRIAGE_PLANNING_MODE,
    )
    external_search_step, external_search_execution = execute_step(
        state=state,
        step_index=3,
        question=question,
        tool_name="document_search",
        action="query",
        target=build_external_evidence_query(
            service=service,
            environment=environment,
            symptom=symptom,
            status_output=status_output,
        ),
        arguments={
            "max_results": "3",
            "search_mode": "qdrant",
            "source_prefixes": EXTERNAL_EVIDENCE_PREFIXES,
        },
        planning_mode=INCIDENT_TRIAGE_PLANNING_MODE,
    )
    return (
        [search_step, external_search_step],
        search_execution.model_dump().get("output", {}),
        external_search_execution.model_dump().get("output", {}),
    )


def run_prepare_incident_ticket_skill(
    *,
    state: AgentState,
    question: str,
    service: str,
    environment: str,
    severity: str,
    symptom: str,
    status_output: dict[str, Any],
    external_search_output: dict[str, Any],
    execute_step: ExecuteStep,
) -> tuple[list[dict[str, Any]], dict[str, Any], str, dict[str, Any]]:
    status_summary = status_output.get("summary") or f"{service} is degraded in {environment}."
    draft_step, draft_execution = execute_step(
        state=state,
        step_index=4,
        question=question,
        tool_name="ticketing",
        action="draft",
        target=service,
        arguments={
            "severity": severity,
            "environment": environment,
            "supporting_summary": (
                f"{status_summary} Observed symptom: {symptom}. "
                f"External evidence: {external_search_output.get('matched_documents', '')}."
            ).strip(),
        },
        planning_mode=INCIDENT_TRIAGE_PLANNING_MODE,
    )
    draft_output = draft_execution.model_dump().get("output", {})
    clarification_question, clarification_plan = build_ticket_submission_confirmation(
        service=service,
        environment=environment,
        draft_output=draft_output,
    )
    return [draft_step], draft_output, clarification_question, clarification_plan
