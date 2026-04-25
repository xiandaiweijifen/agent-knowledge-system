from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.agent_v2.skills.incident_triage import select_evidence_filename
from app.services.agent_v2.state import AgentState


SERVICE_RUNTIME_REVIEW_PLANNING_MODE = "agent_v2_service_runtime_review"

ExecuteStep = Callable[..., tuple[dict[str, Any], Any]]


def build_runtime_review_summary(
    *,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict[str, Any],
    guidance_output: dict[str, Any] | None,
) -> str:
    health = str(status_output.get("health") or status_output.get("status") or "unknown").lower()
    status_summary = str(status_output.get("summary") or f"{service} status checked in {environment}.").strip()
    alerts = status_output.get("active_alerts")
    active_alerts = [str(item).strip() for item in alerts if str(item).strip()] if isinstance(alerts, list) else []
    matched_documents = (
        str(guidance_output.get("matched_documents") or "").strip()
        if isinstance(guidance_output, dict)
        else ""
    )
    guidance_clause = f" Relevant guidance came from {matched_documents}." if matched_documents else ""

    if health in {"healthy", "ok", "nominal"}:
        return (
            f"Service runtime review for {service} in {environment} found the service healthy. "
            f"{status_summary} No incident action is recommended right now.{guidance_clause}"
        )

    recommendation = (
        f" Recommended checks: inspect active alerts {', '.join(active_alerts)}."
        if active_alerts
        else f" Recommended checks: review the service runbook for {symptom} handling."
    )
    return (
        f"Service runtime review for {service} in {environment} found the service {health}. "
        f"{status_summary}{recommendation}{guidance_clause}"
    )


def run_collect_runtime_guidance_skill(
    *,
    state: AgentState,
    question: str,
    service: str,
    symptom: str,
    status_output: dict[str, Any],
    execute_step: ExecuteStep,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
        planning_mode=SERVICE_RUNTIME_REVIEW_PLANNING_MODE,
    )
    return [search_step], search_execution.model_dump().get("output", {})
