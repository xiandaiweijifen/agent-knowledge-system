"""Specialized sub-agent entry nodes for the supervisor graph."""

from app.services.agent_v2.nodes.clarify import clarify_node
from app.services.agent_v2.nodes.retrieval import retrieval_node
from app.services.agent_v2.nodes.tool_exec import tool_exec_node
from app.services.agent_v2.state import AgentState


def knowledge_specialist_node(state: AgentState) -> dict:
    specialist_update = retrieval_node(state)
    return {
        **specialist_update,
        "supervisor_agent": state.get("supervisor_agent") or "knowledge_specialist",
    }


def operations_specialist_node(state: AgentState) -> dict:
    specialist_update = tool_exec_node(state)
    return {
        **specialist_update,
        "supervisor_agent": state.get("supervisor_agent") or "operations_specialist",
    }


def clarification_specialist_node(state: AgentState) -> dict:
    specialist_update = clarify_node(state)
    return {
        **specialist_update,
        "supervisor_agent": state.get("supervisor_agent") or "clarification_specialist",
    }
