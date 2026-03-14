from app.schemas.query import QueryResponse
from app.services.llm.answer_service import generate_rag_answer
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks


def run_query(filename: str, question: str, top_k: int = 3) -> QueryResponse:
    """Execute the retrieval and answer-generation flow for a query."""
    retrieval_result = retrieve_relevant_chunks(
        filename=filename,
        query_text=question,
        top_k=top_k,
    )
    answer_result = generate_rag_answer(
        question=retrieval_result.question,
        matches=[match.model_dump() for match in retrieval_result.matches],
    )

    return QueryResponse(
        filename=retrieval_result.filename,
        question=retrieval_result.question,
        answer=answer_result["answer"],
        answer_source=answer_result["answer_source"],
        model=answer_result["model"],
        answered_at=answer_result["answered_at"],
        answer_latency_ms=answer_result["answer_latency_ms"],
        chat_provider=answer_result["chat_provider"],
        chat_model=answer_result["chat_model"],
        retrieval=retrieval_result,
    )
