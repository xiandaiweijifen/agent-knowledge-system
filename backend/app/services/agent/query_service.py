from app.services.llm.answer_service import generate_rag_answer
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks


def run_query(filename: str, question: str, top_k: int = 3) -> dict:
    """Execute the retrieval and answer-generation flow for a query."""
    retrieval_result = retrieve_relevant_chunks(
        filename=filename,
        query_text=question,
        top_k=top_k,
    )
    answer_result = generate_rag_answer(
        question=retrieval_result["question"],
        matches=retrieval_result["matches"],
    )

    return {
        "filename": retrieval_result["filename"],
        "question": retrieval_result["question"],
        "answer": answer_result["answer"],
        "answer_source": answer_result["answer_source"],
        "model": answer_result["model"],
        "retrieval": retrieval_result,
    }
