"""Answer node — generates the final response."""

from app.services.agent_v2.state import AgentState


def answer_node(state: AgentState) -> dict:
    """
    Preserve an existing answer when an upstream node already produced one.
    Otherwise return a placeholder answer for now.
    Package 9 will wire in generate_rag_answer().
    """
    if state.get("answer"):
        return {
            "answer": state["answer"],
            "answer_source": state.get("answer_source") or "stub",
            "workflow_status": "completed",
        }
    return {
        "answer": "Answer will be generated here.",
        "answer_source": "stub",
        "workflow_status": "completed",
    }
