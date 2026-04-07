"""Tool execution node — runs tool actions requested by the router."""

from app.services.agent_v2.state import AgentState


def tool_exec_node(state: AgentState) -> dict:
    """
    Stub: no-op for now.
    Package 9 will wire in MCP / existing tool adapters.
    """
    return {"tool_chain": [], "workflow_status": "in_progress"}
