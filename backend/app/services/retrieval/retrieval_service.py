from math import sqrt
from time import perf_counter

from app.schemas.indexing import PersistedEmbeddingDocument
from app.schemas.query import (
    QueryDiagnosticsResponse,
    RetrievalDiagnosticsSummary,
    RetrievalResult,
    RetrievedChunkMatch,
)
from app.services.indexing.embedding_service import (
    generate_query_embedding,
    load_persisted_embeddings,
)
from app.services.ingestion.document_service import build_utc_timestamp


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for two vectors with the same dimension."""
    if len(left) != len(right):
        raise ValueError("embedding_dimension_mismatch")

    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    dot_product = sum(left[index] * right[index] for index in range(len(left)))
    return dot_product / (left_norm * right_norm)


def retrieve_relevant_chunks(
    filename: str,
    query_text: str,
    top_k: int = 3,
) -> RetrievalResult:
    """Retrieve the most relevant chunks from persisted embeddings."""
    if top_k <= 0:
        raise ValueError("top_k_must_be_positive")

    normalized_query = query_text.strip()

    if not normalized_query:
        raise ValueError("question_must_not_be_empty")

    retrieval_result, _, _ = build_retrieval_outputs(
        filename=filename,
        query_text=normalized_query,
        top_k=top_k,
        candidate_count=top_k,
    )
    return retrieval_result


def build_retrieval_outputs(
    filename: str,
    query_text: str,
    top_k: int,
    candidate_count: int,
) -> tuple[RetrievalResult, list[RetrievedChunkMatch], int]:
    """Build retrieval outputs for both query and diagnostics endpoints."""
    if candidate_count <= 0:
        raise ValueError("candidate_count_must_be_positive")

    retrieval_started = perf_counter()
    embedding_payload = PersistedEmbeddingDocument.model_validate(
        load_persisted_embeddings(filename)
    )
    query_embedding_provider, query_embedding_model, query_vector = generate_query_embedding(
        query_text,
        embedding_provider=embedding_payload.embedding_provider,
        embedding_model=embedding_payload.embedding_model,
        vector_dim=embedding_payload.vector_dim,
    )

    scored_chunks = []

    for embedding in embedding_payload.embeddings:
        scored_chunks.append(
            RetrievedChunkMatch(
                chunk_id=embedding.chunk_id,
                chunk_index=embedding.chunk_index,
                source_filename=embedding.source_filename,
                source_suffix=embedding.source_suffix,
                char_count=embedding.char_count,
                content=embedding.content,
                score=round(
                    cosine_similarity(query_vector, embedding.vector),
                    6,
                ),
            )
        )

    scored_chunks.sort(key=lambda item: item.score, reverse=True)
    top_chunks = scored_chunks[:top_k]
    diagnostic_candidates = scored_chunks[:candidate_count]
    retrieval_latency_ms = round((perf_counter() - retrieval_started) * 1000, 3)

    retrieval_result = RetrievalResult(
        filename=embedding_payload.filename,
        embedding_provider=embedding_payload.embedding_provider,
        embedding_model=embedding_payload.embedding_model,
        vector_dim=embedding_payload.vector_dim,
        question=query_text,
        top_k=top_k,
        retrieved_at=build_utc_timestamp(),
        retrieval_latency_ms=retrieval_latency_ms,
        query_embedding_provider=query_embedding_provider,
        query_embedding_model=query_embedding_model,
        matches=top_chunks,
    )

    return retrieval_result, diagnostic_candidates, len(scored_chunks)


def retrieve_relevant_chunks_with_diagnostics(
    filename: str,
    query_text: str,
    top_k: int = 3,
    candidate_count: int = 10,
) -> QueryDiagnosticsResponse:
    """Return retrieval results together with ranked candidate diagnostics."""
    if top_k <= 0:
        raise ValueError("top_k_must_be_positive")

    normalized_query = query_text.strip()

    if not normalized_query:
        raise ValueError("question_must_not_be_empty")

    retrieval_result, diagnostic_candidates, total_scored_chunks = build_retrieval_outputs(
        filename=filename,
        query_text=normalized_query,
        top_k=top_k,
        candidate_count=candidate_count,
    )
    candidate_scores = [candidate.score for candidate in diagnostic_candidates]

    if candidate_scores:
        max_score = max(candidate_scores)
        min_score = min(candidate_scores)
        mean_score = round(sum(candidate_scores) / len(candidate_scores), 6)
    else:
        max_score = 0.0
        min_score = 0.0
        mean_score = 0.0

    diagnostics = RetrievalDiagnosticsSummary(
        total_scored_chunks=total_scored_chunks,
        returned_candidate_count=len(diagnostic_candidates),
        max_score=max_score,
        min_score=min_score,
        mean_score=mean_score,
    )

    return QueryDiagnosticsResponse(
        filename=retrieval_result.filename,
        question=retrieval_result.question,
        retrieval=retrieval_result,
        diagnostics=diagnostics,
        candidates=diagnostic_candidates,
    )
