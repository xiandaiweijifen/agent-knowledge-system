from typing import Any

from app.services.agent_v2.tool_extraction import _extract_step_output


def _build_workflow_policy(
    *,
    workflow_family: str,
    workflow_status: str,
    terminal_reason: str | None,
    tool_chain: list[dict[str, Any]],
) -> tuple[str | None, list[str]]:
    normalized_terminal_reason = str(terminal_reason or "").strip().lower()

    if workflow_family == "incident_triage":
        status_output = _extract_step_output(tool_chain, "system_status")
        health = str(status_output.get("health") or status_output.get("status") or "").strip().lower()

        if normalized_terminal_reason == "ticket_submitted":
            return "ticket_submitted", []
        if normalized_terminal_reason == "ticket_submission_cancelled":
            return "ticket_submission_cancelled", ["review_ticket_artifact"]
        if workflow_status == "clarification_required":
            return "ticket_draft_ready", ["submit_ticket", "cancel_ticket"]
        if normalized_terminal_reason == "no_incident_detected" or health in {"healthy", "ok", "nominal"}:
            return "no_incident_detected", ["monitor_service"]
        return "investigate_further", ["review_evidence", "inspect_service_health"]

    if workflow_family == "service_runtime_review":
        status_output = _extract_step_output(tool_chain, "system_status")
        dependency_output = _extract_step_output(tool_chain, "service_dependencies")
        health = str(status_output.get("health") or status_output.get("status") or "").strip().lower()
        nested_snapshot = (
            status_output.get("status_snapshot")
            if isinstance(status_output.get("status_snapshot"), dict)
            else {}
        )
        scenario_id = str(
            status_output.get("requested_scenario")
            or status_output.get("scenario_id")
            or (nested_snapshot.get("scenario_id") if isinstance(nested_snapshot, dict) else "")
            or ""
        ).strip().lower()
        primary_dependency = str(dependency_output.get("suspected_primary_dependency") or "").strip()
        active_alerts = status_output.get("active_alerts")
        has_alerts = isinstance(active_alerts, list) and any(str(item).strip() for item in active_alerts)

        if health in {"healthy", "ok", "nominal"}:
            return "no_action_needed", ["monitor_service"]
        if scenario_id == "recovery_in_progress":
            return "monitor_closely", ["monitor_service", "compare_against_healthy_baseline"]
        if primary_dependency:
            if scenario_id in {"timeout_spike", "db_latency_spike"} or has_alerts:
                return "inspect_dependencies", [
                    "inspect_primary_dependency",
                    "open_runbook",
                    "prepare_incident_triage",
                ]
            return "inspect_dependencies", ["inspect_primary_dependency", "open_runbook"]
        if has_alerts:
            return "inspect_active_alerts", [
                "inspect_active_alerts",
                "open_runbook",
                "prepare_incident_triage",
            ]
        return "review_runbook", ["open_runbook"]

    if workflow_family == "knowledge_retrieval" and workflow_status == "completed":
        return "answer_generated", []
    if workflow_status == "clarification_required":
        return "clarification_required", []
    if workflow_status == "failed":
        return "workflow_failed", []
    return None, []


def _is_ticket_submission_confirmation_plan(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict):
        return False
    return str(plan.get("confirmation_kind") or "").strip().lower() == "ticket_submission"


def _interpret_ticket_submission_confirmation(
    clarification_context: dict[str, str] | None,
) -> bool | None:
    if not isinstance(clarification_context, dict):
        return None

    for key in ("submission_confirmation", "confirmation", "confirm", "submit_ticket", "approve"):
        raw_value = clarification_context.get(key)
        if not isinstance(raw_value, str):
            continue
        normalized = raw_value.strip().lower()
        if normalized in {"yes", "y", "true", "confirm", "confirmed", "submit", "approved"}:
            return True
        if normalized in {"no", "n", "false", "cancel", "decline", "declined", "reject", "rejected"}:
            return False
    return None
