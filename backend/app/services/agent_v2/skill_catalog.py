import copy
from typing import Any


# Each skill declares which tools it owns per workflow_family via "tool_ownership".
# _resolve_step_skill_id uses this to look up skill ID without an if-elif tree.
SKILL_CATALOG: dict[str, dict[str, Any]] = {
    "retrieve_grounded_knowledge": {
        "skill_label": "Retrieve Grounded Knowledge",
        "description": "Retrieve and ground an answer against indexed knowledge assets.",
        "owned_tools": ["document_search"],
        "workflow_families": ["knowledge_retrieval"],
        "tool_ownership": {
            "knowledge_retrieval": ["document_search"],
        },
    },
    "resolve_missing_context": {
        "skill_label": "Resolve Missing Context",
        "description": "Collect clarification data before the workflow can continue safely.",
        "owned_tools": [],
        "workflow_families": ["clarification", "incident_triage", "tool_execution"],
        "tool_ownership": {},
    },
    "execute_operational_tool": {
        "skill_label": "Execute Operational Tool",
        "description": "Execute a single operational tool request with structured tracing.",
        "owned_tools": ["system_status", "document_search", "ticketing"],
        "workflow_families": ["tool_execution"],
        "tool_ownership": {
            "tool_execution": ["system_status", "document_search", "ticketing"],
        },
    },
    "review_service_health": {
        "skill_label": "Review Service Health",
        "description": "Inspect the target service health and normalize the runtime status snapshot.",
        "owned_tools": ["system_status"],
        "workflow_families": ["incident_triage", "service_runtime_review"],
        "tool_ownership": {
            "incident_triage": ["system_status"],
            "service_runtime_review": ["system_status"],
        },
    },
    "collect_runtime_guidance": {
        "skill_label": "Collect Runtime Guidance",
        "description": "Retrieve runbook guidance to recommend the next runtime checks for a service.",
        "owned_tools": ["document_search"],
        "workflow_families": ["service_runtime_review"],
        "tool_ownership": {
            "service_runtime_review": ["document_search"],
        },
    },
    "inspect_service_dependencies": {
        "skill_label": "Inspect Service Dependencies",
        "description": "Inspect structured dependency data to identify the most likely downstream dependency to check next.",
        "owned_tools": ["service_dependencies"],
        "workflow_families": ["service_runtime_review"],
        "tool_ownership": {
            "service_runtime_review": ["service_dependencies"],
        },
    },
    "collect_incident_evidence": {
        "skill_label": "Collect Incident Evidence",
        "description": "Gather runbook and external evidence that supports incident diagnosis.",
        "owned_tools": ["document_search"],
        "workflow_families": ["incident_triage"],
        "tool_ownership": {
            "incident_triage": ["document_search"],
        },
    },
    "prepare_incident_ticket": {
        "skill_label": "Prepare Incident Ticket",
        "description": "Prepare, confirm, and submit incident tickets with explicit operator control.",
        "owned_tools": ["ticketing"],
        "workflow_families": ["incident_triage"],
        "tool_ownership": {
            "incident_triage": ["ticketing"],
        },
    },
}


def _default_skill_for_family(workflow_family: str) -> str:
    if workflow_family == "clarification":
        return "resolve_missing_context"
    if workflow_family == "knowledge_retrieval":
        return "retrieve_grounded_knowledge"
    return "execute_operational_tool"


def _build_skill_definition(skill_id: str) -> dict[str, Any]:
    definition = SKILL_CATALOG[skill_id]
    return {
        "skill_id": skill_id,
        "skill_label": definition["skill_label"],
        "description": definition["description"],
        "owned_tools": definition["owned_tools"],
        "workflow_families": definition["workflow_families"],
    }


def _resolve_workflow_family(
    final_state: dict[str, Any],
    interrupt_payload: dict[str, Any] | None,
) -> str:
    if interrupt_payload is not None:
        clarification_plan = final_state.get("clarification_plan")
        if (
            isinstance(clarification_plan, dict)
            and clarification_plan.get("confirmation_kind") == "ticket_submission"
        ):
            return "incident_triage"
        return "clarification"

    if final_state.get("answer_source") == "local_incident_triage":
        return "incident_triage"
    if final_state.get("answer_source") == "local_service_runtime_review":
        return "service_runtime_review"

    route = final_state.get("route") or "knowledge_retrieval"
    if route == "tool_execution":
        return "tool_execution"
    if route == "clarification_needed":
        return "clarification"
    return "knowledge_retrieval"


def _resolve_step_skill_id(step: dict[str, Any], workflow_family: str) -> str:
    tool_name = str((step.get("tool_plan") or {}).get("tool_name") or "").strip().lower()
    for skill_id, definition in SKILL_CATALOG.items():
        owned = definition.get("tool_ownership", {}).get(workflow_family, [])
        if tool_name in owned:
            return skill_id
    return _default_skill_for_family(workflow_family)


def _build_skill_summary(
    skill_id: str,
    steps: list[dict[str, Any]],
    workflow_family: str,
) -> str:
    if skill_id == "review_service_health":
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            summary = str(output.get("summary") or "").strip()
            if summary:
                return summary
        return "Reviewed the target service health."
    if skill_id == "collect_incident_evidence":
        matched_documents: list[str] = []
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            raw_documents = str(output.get("matched_documents") or "").strip()
            if raw_documents:
                matched_documents.extend(
                    item.strip() for item in raw_documents.split(",") if item.strip()
                )
        if matched_documents:
            unique_documents = list(dict.fromkeys(matched_documents))
            return f"Collected supporting evidence from {', '.join(unique_documents[:3])}."
        return "Collected supporting incident evidence."
    if skill_id == "collect_runtime_guidance":
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            matched_documents = str(output.get("matched_documents") or "").strip()
            if matched_documents:
                return f"Collected runtime guidance from {matched_documents}."
        return "Collected runtime guidance for the requested service."
    if skill_id == "inspect_service_dependencies":
        for step in steps:
            output = (step.get("tool_execution") or {}).get("output") or {}
            primary_dependency = str(output.get("suspected_primary_dependency") or "").strip()
            if primary_dependency:
                return f"Identified {primary_dependency} as the most likely downstream dependency to inspect."
        return "Inspected the service dependency map."
    if skill_id == "prepare_incident_ticket":
        last_step = steps[-1] if steps else {}
        output = (last_step.get("tool_execution") or {}).get("output") or {}
        ticket_id = str(output.get("ticket_id") or "").strip()
        submission_state = str(output.get("submission_state") or output.get("status") or "").strip()
        if ticket_id and submission_state:
            return f"Ticket {ticket_id} is currently in state {submission_state}."
        if ticket_id:
            return f"Prepared ticket {ticket_id}."
        return "Prepared incident ticket workflow state."
    if skill_id == "retrieve_grounded_knowledge":
        return "Retrieved grounded knowledge for the requested question."
    if skill_id == "resolve_missing_context":
        return "Awaiting clarification before continuing workflow execution."
    if workflow_family == "tool_execution":
        return "Executed the planned operational tool sequence."
    return "Prepared reusable skill metadata for the workflow."


def _build_skill_metadata(
    final_state: dict[str, Any],
    interrupt_payload: dict[str, Any] | None,
    tool_chain: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    workflow_family = _resolve_workflow_family(final_state, interrupt_payload)
    enriched_tool_chain: list[dict[str, Any]] = []
    skill_steps: dict[str, list[dict[str, Any]]] = {}

    for step in tool_chain:
        if not isinstance(step, dict):
            continue
        skill_id = _resolve_step_skill_id(step, workflow_family)
        enriched_step = copy.deepcopy(step)
        enriched_step["skill_id"] = skill_id
        enriched_step["skill_label"] = SKILL_CATALOG[skill_id]["skill_label"]
        enriched_tool_chain.append(enriched_step)
        skill_steps.setdefault(skill_id, []).append(enriched_step)

    if not skill_steps:
        fallback_skill_id = _default_skill_for_family(workflow_family)
        return workflow_family, enriched_tool_chain, [_build_skill_definition(fallback_skill_id)], [
            {
                "skill_id": fallback_skill_id,
                "skill_label": SKILL_CATALOG[fallback_skill_id]["skill_label"],
                "status": final_state.get("workflow_status") or "completed",
                "summary": _build_skill_summary(fallback_skill_id, [], workflow_family),
                "tool_names": SKILL_CATALOG[fallback_skill_id]["owned_tools"],
            }
        ]

    available_skills = [_build_skill_definition(skill_id) for skill_id in skill_steps]
    skill_trace = [
        {
            "skill_id": skill_id,
            "skill_label": SKILL_CATALOG[skill_id]["skill_label"],
            "status": final_state.get("workflow_status") or "completed",
            "summary": _build_skill_summary(skill_id, steps, workflow_family),
            "tool_names": list(
                dict.fromkeys(
                    str((step.get("tool_plan") or {}).get("tool_name") or "")
                    for step in steps
                    if (step.get("tool_plan") or {}).get("tool_name")
                )
            ),
        }
        for skill_id, steps in skill_steps.items()
    ]
    return workflow_family, enriched_tool_chain, available_skills, skill_trace
