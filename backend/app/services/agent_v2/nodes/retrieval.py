"""Retrieval node — fetches relevant chunks for the question."""

from app.services.agent.query_service import run_query
from app.services.agent_v2.state import AgentState


def retrieval_node(state: AgentState) -> dict:
    """
    Execute the current retrieval + answer pipeline inside the graph.
    If no filename is available, leave retrieval empty and allow the answer
    node to provide a placeholder until a broader search flow is added.
    """
    filename = (state.get("filename") or "").strip()
    if not filename:
        return {
            "retrieval_result": None,
            "workflow_status": "in_progress",
        }

    try:
        query_response = run_query(
            filename=filename,
            question=state["question"],
            top_k=state["top_k"],
        )
    except Exception as exc:
        return {
            "retrieval_result": None,
            "workflow_status": "failed",
            "failure_stage": "knowledge_retrieval",
            "retry_state": "not_applicable",
            "retry_count": 0,
            "error": str(exc),
        }
    return {
        "retrieval_result": query_response.retrieval.model_dump(),
        "answer": query_response.answer,
        "answer_source": query_response.answer_source,
        "model": query_response.model,
        "answered_at": query_response.answered_at,
        "answer_latency_ms": query_response.answer_latency_ms,
        "chat_provider": query_response.chat_provider,
        "chat_model": query_response.chat_model,
        "workflow_status": "in_progress",
        "failure_stage": None,
        "retry_state": "not_applicable",
        "retry_count": 0,
    }
