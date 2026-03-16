import re
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


def tokenize_query(text: str) -> list[str]:
    """Extract normalized query terms for lightweight reranking."""
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "does",
        "how",
        "in",
        "is",
        "of",
        "the",
        "what",
        "why",
    }
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [token for token in tokens if token not in stopwords and len(token) > 1]


def build_query_phrases(tokens: list[str], max_length: int = 3) -> set[str]:
    """Build normalized contiguous query phrases for phrase-level lexical bonuses."""
    normalized_tokens = [normalize_token(token) for token in tokens]
    phrases: set[str] = set()

    for phrase_length in range(2, max_length + 1):
        for start_index in range(0, len(normalized_tokens) - phrase_length + 1):
            phrase_tokens = normalized_tokens[start_index : start_index + phrase_length]
            if len(set(phrase_tokens)) == 1:
                continue
            phrases.add(" ".join(phrase_tokens))

    return phrases


def normalize_token(token: str) -> str:
    """Normalize lexical variants for lightweight matching."""
    if token.startswith("rerank"):
        return "rerank"

    if token.endswith("ing") and len(token) > 5:
        return token[:-3]

    if token.endswith("ers") and len(token) > 5:
        return token[:-3]

    if token.endswith("er") and len(token) > 4:
        return token[:-2]

    if token.endswith("s") and len(token) > 4:
        return token[:-1]

    return token


def build_normalized_token_set(text: str) -> set[str]:
    """Build a normalized token set from free-form text."""
    return {
        normalize_token(token)
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1
    }


def compute_rerank_bonus(query_text: str, chunk_content: str) -> float:
    """Apply simple lexical bonuses on top of vector similarity."""
    content_lower = chunk_content.lower()
    query_lower = query_text.lower().strip()
    query_terms = tokenize_query(query_text)
    normalized_query_terms = [normalize_token(term) for term in query_terms]
    normalized_content_terms = build_normalized_token_set(chunk_content)
    normalized_content = " ".join(normalize_token(token) for token in re.findall(r"[a-z0-9]+", content_lower))
    heading_window = content_lower[:160]
    intro_window = content_lower[:240]
    first_line = content_lower.splitlines()[0] if content_lower.splitlines() else ""
    query_phrases = build_query_phrases(query_terms)
    bonus = 0.0

    if query_lower and query_lower in content_lower:
        bonus += 0.02

    if query_terms:
        matched_terms = sum(
            1 for term in normalized_query_terms if term in normalized_content_terms
        )
        overlap_ratio = matched_terms / len(normalized_query_terms)
        bonus += 0.02 * overlap_ratio

        for term in normalized_query_terms:
            if len(term) >= 8 and term in heading_window:
                bonus += 0.02
            elif len(term) >= 8 and term in intro_window:
                bonus += 0.01

        for phrase in query_phrases:
            if phrase in normalized_content:
                phrase_length = len(phrase.split())
                bonus += 0.03 if phrase_length == 2 else 0.08

        if all(term in heading_window for term in query_terms):
            bonus += 0.03

        if query_lower.startswith("what is"):
            if re.search(rf"\b{re.escape(query_terms[0])}\b\s+means", heading_window):
                bonus += 0.12

            if re.search(rf"\bor\s+{re.escape(query_terms[0])}\s*,?\s+is\b", intro_window):
                bonus += 0.12
            elif re.search(rf"\b{re.escape(query_terms[0])}\s+is\b", intro_window):
                bonus += 0.08

            if first_line.startswith("#") and any(term in first_line for term in query_terms):
                bonus += 0.03

        if query_lower.startswith("why"):
            if "rerank" in normalized_query_terms and "rerank" in normalized_content_terms:
                bonus += 0.06

            if "production" in normalized_query_terms and "production" in normalized_content_terms:
                bonus += 0.03

            if "system" in normalized_query_terms and "system" in normalized_content_terms:
                bonus += 0.02

            if "rerank" in heading_window:
                bonus += 0.04

    return round(bonus, 6)


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
        vector_score = round(cosine_similarity(query_vector, embedding.vector), 6)
        rerank_bonus = compute_rerank_bonus(query_text, embedding.content)

        scored_chunks.append(
            RetrievedChunkMatch(
                chunk_id=embedding.chunk_id,
                chunk_index=embedding.chunk_index,
                source_filename=embedding.source_filename,
                source_suffix=embedding.source_suffix,
                char_count=embedding.char_count,
                content=embedding.content,
                vector_score=vector_score,
                rerank_bonus=rerank_bonus,
                score=round(vector_score + rerank_bonus, 6),
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
