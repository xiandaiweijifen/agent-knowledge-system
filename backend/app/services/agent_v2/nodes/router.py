"""Router node — decides which path to take next."""

from app.services.agent_v2.state import AgentState


def router_node(state: AgentState) -> dict:
    """
    Stub: passes through a pre-set route, defaults to knowledge_retrieval.
    Package 8 will replace this with LLM Function Calling.
    """
    route = state.get("route") or "knowledge_retrieval"
    return {"route": route, "workflow_status": "in_progress"}


def route_decision(state: AgentState) -> str:
    """Conditional edge function — maps route value to next node name."""
    route = state.get("route", "knowledge_retrieval")
    mapping = {
        "knowledge_retrieval": "retrieval",
        "tool_execution": "tool_exec",
        "clarification_needed": "clarify",
    }
    return mapping.get(route, "retrieval")
