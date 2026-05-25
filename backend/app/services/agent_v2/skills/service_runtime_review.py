from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.agent_v2.skills.incident_triage import (
    _ENVIRONMENT_PATTERN,
    _SERVICE_PATTERN,
    _SYMPTOM_PATTERN,
    _normalize_skill_environment,
    select_evidence_filename,
)
from app.services.agent_v2.state import AgentState


SERVICE_RUNTIME_REVIEW_PLANNING_MODE = "agent_v2_service_runtime_review"


def extract_context(question: str) -> dict[str, str] | None:
    """Extract service runtime review context (service, environment, symptom) from a question."""
    service_match = _SERVICE_PATTERN.search(question)
    if service_match is None:
        return None

    environment_match = _ENVIRONMENT_PATTERN.search(question)
    symptom_match = _SYMPTOM_PATTERN.search(question)
    return {
        "service": service_match.group(1),
        "environment": _normalize_skill_environment(environment_match.group(1) if environment_match else None),
        "symptom": (symptom_match.group(1).lower() if symptom_match else "health"),
    }

ExecuteStep = Callable[..., tuple[dict[str, Any], Any]]


def build_runtime_review_summary(
    *,
    service: str,
    environment: str,
    symptom: str,
    status_output: dict[str, Any],
    dependency_output: dict[str, Any] | None,
    guidance_output: dict[str, Any] | None,
) -> str:
    health = str(status_output.get("health") or status_output.get("status") or "unknown").lower()
    status_summary = str(status_output.get("summary") or f"{service} status checked in {environment}.").strip()
    alerts = status_output.get("active_alerts")
    active_alerts = [str(item).strip() for item in alerts if str(item).strip()] if isinstance(alerts, list) else []
    primary_dependency = (
        str(dependency_output.get("suspected_primary_dependency") or "").strip()
        if isinstance(dependency_output, dict)
        else ""
    )
    dependency_clause = (
        f" Likely dependency to inspect next: {primary_dependency}."
        if primary_dependency
        else ""
    )
    matched_documents = (
        str(guidance_output.get("matched_documents") or "").strip()
        if isinstance(guidance_output, dict)
        else ""
    )
    guidance_clause = f" Relevant guidance came from {matched_documents}." if matched_documents else ""

    if health in {"healthy", "ok", "nominal"}:
        return (
            f"Service runtime review for {service} in {environment} found the service healthy. "
            f"{status_summary} No incident action is recommended right now.{dependency_clause}{guidance_clause}"
        )

    recommendation = (
        f" Recommended checks: inspect active alerts {', '.join(active_alerts)}."
        if active_alerts
        else f" Recommended checks: review the service runbook for {symptom} handling."
    )
    return (
        f"Service runtime review for {service} in {environment} found the service {health}. "
        f"{status_summary}{recommendation}{dependency_clause}{guidance_clause}"
    )


def run_collect_dependency_context_skill(
    *,
    state: AgentState,
    question: str,
    service: str,
    environment: str,
    status_output: dict[str, Any],
    execute_step: ExecuteStep,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    alerts = status_output.get("active_alerts")
    failure_signal = ""
    if isinstance(alerts, list):
        for item in alerts:
            candidate = str(item).strip()
            if candidate:
                failure_signal = candidate
                break

    dependency_step, dependency_execution = execute_step(
        state=state,
        step_index=2,
        question=question,
        tool_name="service_dependencies",
        action="query",
        target=service,
        arguments={
            "environment": environment,
            **({"failure_signal": failure_signal} if failure_signal else {}),
        },
        planning_mode=SERVICE_RUNTIME_REVIEW_PLANNING_MODE,
    )
    return [dependency_step], dependency_execution.model_dump().get("output", {})


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
        step_index=3,
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
