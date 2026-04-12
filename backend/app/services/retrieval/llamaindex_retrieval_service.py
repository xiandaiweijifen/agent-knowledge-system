"""
LlamaIndex-based retrieval service.

Wraps query_llamaindex_index() and converts results into the existing
RetrievalResult / RetrievedChunkMatch schema so the rest of the system
(query_service, orchestrator, evaluation) requires zero changes.
"""

from __future__ import annotations

import logging
from time import perf_counter

from app.schemas.query import RetrievalResult, RetrievedChunkMatch
from app.services.ingestion.document_service import (
    build_utc_timestamp,
    list_llamaindex_ready_documents,
)
from app.services.ingestion.llamaindex_ingestion_service import (
    LLAMAINDEX_STORE_DIR,
    query_llamaindex_index,
)
from app.services.retrieval.retrieval_service import (
    compute_rerank_bonus,
    normalize_query_text,
)

logger = logging.getLogger(__name__)
CORPUS_SOURCE_PENALTY = 0.08


def _index_exists(filename: str) -> bool:
    """Return True if a persisted LlamaIndex index exists for this document."""
    from pathlib import Path

    stem = Path(filename).stem
    return (LLAMAINDEX_STORE_DIR / stem / "index_store.json").exists()


def _build_matches_from_raw_results(
    raw_results: list[dict],
    normalized_query: str,
    fallback_filename: str,
) -> list[RetrievedChunkMatch]:
    matches: list[RetrievedChunkMatch] = []

    for result in raw_results:
        metadata = result["metadata"]
        rerank_bonus = compute_rerank_bonus(
            normalized_query,
            result["content"],
            section_title=metadata.get("section_title", ""),
            section_path=metadata.get("section_path", []),
        )
        matches.append(
            RetrievedChunkMatch(
                chunk_id=result["chunk_id"],
                chunk_index=metadata.get("chunk_index", 0),
                source_filename=metadata.get("source_filename", fallback_filename),
                source_suffix=metadata.get("source_suffix", ""),
                char_count=metadata.get("char_count", len(result["content"])),
                section_title=metadata.get("section_title", ""),
                section_path=metadata.get("section_path", []),
                heading_level=metadata.get("heading_level"),
                content=result["content"],
                vector_score=result["score"],
                rerank_bonus=rerank_bonus,
                score=round(result["score"] + rerank_bonus, 6),
            )
        )

    matches.sort(key=lambda match: match.score, reverse=True)
    return matches


def _select_diversified_corpus_matches(
    matches: list[RetrievedChunkMatch],
    top_k: int,
    source_penalty: float = CORPUS_SOURCE_PENALTY,
) -> list[RetrievedChunkMatch]:
    """Greedily diversify corpus results without overpowering base relevance."""
    if len(matches) <= top_k:
        return matches

    remaining = list(matches)
    selected: list[RetrievedChunkMatch] = []
    selected_by_source: dict[str, int] = {}

    while remaining and len(selected) < top_k:
        best_index = 0
        best_adjusted_score = float("-inf")

        for index, match in enumerate(remaining):
            prior_hits = selected_by_source.get(match.source_filename, 0)
            adjusted_score = match.score - (prior_hits * source_penalty)
            if adjusted_score > best_adjusted_score:
                best_adjusted_score = adjusted_score
                best_index = index

        chosen = remaining.pop(best_index)
        selected.append(chosen)
        selected_by_source[chosen.source_filename] = (
            selected_by_source.get(chosen.source_filename, 0) + 1
        )

    return selected


def retrieve_with_llamaindex(
    filename: str,
    query_text: str,
    top_k: int = 3,
) -> RetrievalResult:
    """
    Retrieve chunks using the LlamaIndex VectorStoreIndex.
    Raises FileNotFoundError if no index exists for this document.
    """
    if not _index_exists(filename):
        raise FileNotFoundError(filename)

    started = perf_counter()
    normalized_query = normalize_query_text(query_text)
    raw_results = query_llamaindex_index(filename, normalized_query, top_k=top_k)
    latency_ms = round((perf_counter() - started) * 1000, 3)
    matches = _build_matches_from_raw_results(
        raw_results=raw_results,
        normalized_query=normalized_query,
        fallback_filename=filename,
    )

    return RetrievalResult(
        filename=filename,
        retrieval_scope="document",
        corpus_filenames=[filename],
        embedding_provider="llamaindex",
        embedding_model="llamaindex-simplestore",
        vector_dim=0,
        question=query_text,
        top_k=top_k,
        retrieved_at=build_utc_timestamp(),
        retrieval_latency_ms=latency_ms,
        query_embedding_provider="llamaindex",
        query_embedding_model="llamaindex-simplestore",
        matches=matches,
    )


def retrieve_with_llamaindex_corpus(
    query_text: str,
    top_k: int = 3,
    filenames: list[str] | None = None,
) -> RetrievalResult:
    """Retrieve and merge results across multiple LlamaIndex-ready documents."""
    candidate_filenames = filenames or list_llamaindex_ready_documents()
    ready_filenames = [filename for filename in candidate_filenames if _index_exists(filename)]

    if not ready_filenames:
        raise FileNotFoundError("llamaindex_corpus")

    started = perf_counter()
    normalized_query = normalize_query_text(query_text)
    all_matches: list[RetrievedChunkMatch] = []

    for filename in ready_filenames:
        raw_results = query_llamaindex_index(filename, normalized_query, top_k=top_k)
        all_matches.extend(
            _build_matches_from_raw_results(
                raw_results=raw_results,
                normalized_query=normalized_query,
                fallback_filename=filename,
            )
        )

    all_matches.sort(key=lambda match: match.score, reverse=True)
    selected_matches = _select_diversified_corpus_matches(all_matches, top_k=top_k)
    latency_ms = round((perf_counter() - started) * 1000, 3)

    return RetrievalResult(
        filename=None,
        retrieval_scope="corpus",
        corpus_filenames=ready_filenames,
        embedding_provider="llamaindex",
        embedding_model="llamaindex-simplestore",
        vector_dim=0,
        question=query_text,
        top_k=top_k,
        retrieved_at=build_utc_timestamp(),
        retrieval_latency_ms=latency_ms,
        query_embedding_provider="llamaindex",
        query_embedding_model="llamaindex-simplestore",
        matches=selected_matches,
    )
