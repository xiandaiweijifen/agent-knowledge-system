"""Answer node — generates the final response."""

from app.services.agent_v2.state import AgentState


def answer_node(state: AgentState) -> dict:
    """
    Stub: returns a placeholder answer for now.
    Package 9 will wire in generate_rag_answer().
    """
    return {
        "answer": "Answer will be generated here.",
        "answer_source": "stub",
        "workflow_status": "completed",
    }
