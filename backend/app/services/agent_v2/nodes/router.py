"""Router node - decides which path to take next."""

import re

from app.services.agent.router_service import route_request
from app.services.agent_v2.state import AgentState
from app.services.llm.route_planner_service import generate_llm_route_decision


SUPPORTED_ROUTES = {
    "knowledge_retrieval",
    "tool_execution",
    "clarification_needed",
}

INCIDENT_TRIAGE_PATTERN = re.compile(
    r"\b(check|inspect|investigate|look at)\b.*\b(if|when)\b.*\b(abnormal|degraded|issue|incident)\b.*\b(ticket|draft|prepare)\b",
    re.IGNORECASE,
)
SERVICE_RUNTIME_REVIEW_PATTERN = re.compile(
    r"\b(check|inspect|review|look at|tell me)\b.*\b(status|health|healthy|runtime|running|degraded)\b",
    re.IGNORECASE,
)
SERVICE_PATTERN = re.compile(r"\b([a-z0-9][a-z0-9-]*(?:service|api))\b", re.IGNORECASE)


def _resolve_deterministic_route(question: str) -> dict[str, str] | None:
    normalized_question = question.strip()
    if not normalized_question:
        return None

    if INCIDENT_TRIAGE_PATTERN.search(normalized_question) and SERVICE_PATTERN.search(normalized_question):
        return {
            "route": "tool_execution",
            "route_reason": (
                "The request matches the incident triage workflow pattern, so it should be routed "
                "toward tool execution."
            ),
        }

    if SERVICE_RUNTIME_REVIEW_PATTERN.search(normalized_question) and SERVICE_PATTERN.search(normalized_question):
        return {
            "route": "tool_execution",
            "route_reason": (
                "The request matches the service runtime review workflow pattern, so it should be "
                "routed toward tool execution."
            ),
        }

    return None


def router_node(state: AgentState) -> dict:
    """
    Route the request with a deterministic workflow-first strategy, then LLM,
    then legacy fallback.
    """
    preset_route = state.get("route")
    if isinstance(preset_route, str) and preset_route in SUPPORTED_ROUTES:
        return {
            "route": preset_route,
            "route_reason": state.get("route_reason") or "Precomputed route provided by caller.",
            "route_planning_mode": state.get("route_planning_mode") or "precomputed",
            "workflow_status": "in_progress",
        }

    deterministic_route = _resolve_deterministic_route(state["question"])
    if deterministic_route is not None:
        return {
            "route": deterministic_route["route"],
            "route_reason": deterministic_route["route_reason"],
            "route_planning_mode": "deterministic_workflow_router",
            "workflow_status": "in_progress",
        }

    planning_mode, route_payload = generate_llm_route_decision(
        question=state["question"],
        filename=state.get("filename"),
    )
    if route_payload is not None:
        return {
            "route": route_payload["route"],
            "route_reason": route_payload["route_reason"],
            "route_planning_mode": planning_mode,
            "workflow_status": "in_progress",
        }

    fallback_decision = route_request(
        question=state["question"],
        filename=state.get("filename"),
    )
    return {
        "route": fallback_decision.route_type,
        "route_reason": fallback_decision.route_reason,
        "route_planning_mode": planning_mode,
        "workflow_status": "in_progress",
    }


def route_decision(state: AgentState) -> str:
    """Conditional edge function - maps route value to next node name."""
    route = state.get("route", "knowledge_retrieval")
    mapping = {
        "knowledge_retrieval": "retrieval",
        "tool_execution": "tool_exec",
        "clarification_needed": "clarify",
    }
    return mapping.get(route, "retrieval")
