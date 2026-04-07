"""Retrieval node — fetches relevant chunks for the question."""

from app.services.agent_v2.state import AgentState


def retrieval_node(state: AgentState) -> dict:
    """
    Stub: returns empty retrieval result for now.
    Package 9 will wire in LlamaIndex retrieval.
    """
    return {
        "retrieval_result": {"matches": [], "question": state["question"]},
        "workflow_status": "in_progress",
    }
