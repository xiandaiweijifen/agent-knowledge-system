"""Router node — decides which path to take next."""

from app.services.agent.router_service import route_request
from app.services.agent_v2.state import AgentState
from app.services.llm.route_planner_service import generate_llm_route_decision


SUPPORTED_ROUTES = {
    "knowledge_retrieval",
    "tool_execution",
    "clarification_needed",
}


def router_node(state: AgentState) -> dict:
    """
    Route the request with an LLM-first strategy and deterministic fallback.
    Explicit pre-set route values are preserved to keep tests and manual overrides stable.
    """
    preset_route = state.get("route")
    if isinstance(preset_route, str) and preset_route in SUPPORTED_ROUTES:
        return {
            "route": preset_route,
            "route_reason": state.get("route_reason") or "Precomputed route provided by caller.",
            "route_planning_mode": state.get("route_planning_mode") or "precomputed",
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
    """Conditional edge function — maps route value to next node name."""
    route = state.get("route", "knowledge_retrieval")
    mapping = {
        "knowledge_retrieval": "retrieval",
        "tool_execution": "tool_exec",
        "clarification_needed": "clarify",
    }
    return mapping.get(route, "retrieval")
