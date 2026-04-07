"""Clarification node — asks the user for more information."""

from app.services.agent_v2.state import AgentState


def clarify_node(state: AgentState) -> dict:
    """
    Stub: returns a placeholder clarification question.
    Package 10 will replace this with LangGraph interrupt().
    """
    return {
        "clarification_question": "Could you clarify your question?",
        "workflow_status": "clarification_required",
    }
