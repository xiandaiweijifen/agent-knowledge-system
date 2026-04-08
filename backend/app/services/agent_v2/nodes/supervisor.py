"""Supervisor node that selects a specialized sub-agent path."""

from app.services.agent_v2.state import AgentState


SPECIALIST_BY_ROUTE = {
    "knowledge_retrieval": "knowledge_specialist",
    "tool_execution": "operations_specialist",
    "clarification_needed": "clarification_specialist",
}


def supervisor_node(state: AgentState) -> dict:
    route = state.get("route") or "knowledge_retrieval"
    specialist = SPECIALIST_BY_ROUTE.get(route, "knowledge_specialist")
    route_reason = state.get("route_reason") or "No route reason provided."
    return {
        "supervisor_agent": specialist,
        "supervisor_reason": f"Supervisor delegated {route} to {specialist} based on the current route decision.",
        "workflow_status": "in_progress",
        "route_reason": route_reason,
    }


def supervisor_decision(state: AgentState) -> str:
    specialist = state.get("supervisor_agent") or "knowledge_specialist"
    mapping = {
        "knowledge_specialist": "knowledge_specialist",
        "operations_specialist": "operations_specialist",
        "clarification_specialist": "clarification_specialist",
    }
    return mapping.get(specialist, "knowledge_specialist")
