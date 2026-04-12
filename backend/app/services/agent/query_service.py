import logging

from app.core.config import settings
from app.schemas.query import QueryResponse
from app.services.llm.answer_service import generate_rag_answer
from app.services.retrieval.llamaindex_retrieval_service import retrieve_with_llamaindex
from app.services.retrieval.retrieval_service import retrieve_relevant_chunks

logger = logging.getLogger(__name__)


def _normalized_knowledge_retrieval_mode() -> str:
    mode = settings.knowledge_retrieval_mode.strip().lower()
    if mode not in {"llamaindex", "auto", "legacy"}:
        raise ValueError("knowledge_retrieval_mode_invalid")
    return mode


def _retrieve_via_configured_mode(
    filename: str,
    question: str,
    top_k: int,
    execution_context: str,
):
    mode = _normalized_knowledge_retrieval_mode()
    normalized_context = execution_context.strip().lower()

    if normalized_context not in {"standard", "debug", "eval"}:
        raise ValueError("knowledge_retrieval_execution_context_invalid")

    if normalized_context == "standard" and mode != "llamaindex":
        raise ValueError("knowledge_retrieval_mode_requires_debug_or_eval")

    if mode == "legacy":
        logger.debug("retrieval via legacy mode for %s", filename)
        return retrieve_relevant_chunks(
            filename=filename,
            query_text=question,
            top_k=top_k,
        )

    if mode == "llamaindex":
        logger.debug("retrieval via explicit llamaindex mode for %s", filename)
        try:
            return retrieve_with_llamaindex(
                filename=filename,
                query_text=question,
                top_k=top_k,
            )
        except FileNotFoundError as exc:
            raise ValueError("llamaindex_index_not_found") from exc

    try:
        retrieval_result = retrieve_with_llamaindex(
            filename=filename,
            query_text=question,
            top_k=top_k,
        )
        logger.debug("retrieval via llamaindex auto mode for %s", filename)
        return retrieval_result
    except FileNotFoundError:
        logger.debug("llamaindex index not found for %s, using legacy retriever in auto mode", filename)
        return retrieve_relevant_chunks(
            filename=filename,
            query_text=question,
            top_k=top_k,
        )


def run_query(filename: str, question: str, top_k: int = 3) -> QueryResponse:
    """Execute the retrieval and answer-generation flow for a query.

    Retrieval path is selected by `knowledge_retrieval_mode`:
    - `llamaindex`: require a persisted LlamaIndex index
    - `auto`: prefer LlamaIndex and fall back to legacy retrieval
    - `legacy`: force the legacy cosine-similarity retriever
    """
    retrieval_result = _retrieve_via_configured_mode(
        filename=filename,
        question=question,
        top_k=top_k,
        execution_context="standard",
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


def run_query_with_context(
    filename: str,
    question: str,
    top_k: int = 3,
    execution_context: str = "standard",
) -> QueryResponse:
    """Execute the retrieval and answer-generation flow for a query with context-aware mode gating."""
    retrieval_result = _retrieve_via_configured_mode(
        filename=filename,
        question=question,
        top_k=top_k,
        execution_context=execution_context,
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
