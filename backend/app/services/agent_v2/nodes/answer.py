"""Answer node — generates the final response."""

from app.services.agent_v2.state import AgentState


def answer_node(state: AgentState) -> dict:
    """
    Preserve an existing answer when an upstream node already produced one.
    Otherwise return a placeholder answer for now.
    Package 9 will wire in generate_rag_answer().
    """
    if state.get("workflow_status") == "failed":
        return {
            "workflow_status": "failed",
            "error": state.get("error"),
            "failure_stage": state.get("failure_stage"),
            "retry_state": state.get("retry_state"),
            "retry_count": state.get("retry_count", 0),
        }
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
