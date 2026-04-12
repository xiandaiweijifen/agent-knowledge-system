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
    infer_document_kind,
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
CORPUS_KIND_MATCH_BONUS = 0.04
CORPUS_FILENAME_MATCH_BONUS = 0.012
CORPUS_DOCUMENT_SCORE_BONUS_CAP = 0.03
CORPUS_QUERY_HINTS: dict[str, tuple[str, ...]] = {
    "runbook": ("runbook", "runbooks"),
    "incident": ("incident", "incidents", "outage", "sev", "severity"),
    "workflow": ("workflow", "recovery", "resume", "retry", "clarification"),
    "overview": ("overview", "rag", "retrieval", "generation"),
}


def _build_corpus_document_id(filename: str) -> str:
    return filename.strip().lower()


def _build_corpus_node_id(filename: str, chunk_id: str) -> str:
    return f"{_build_corpus_document_id(filename)}::{chunk_id}"


def _index_exists(filename: str) -> bool:
    """Return True if a persisted LlamaIndex index exists for this document."""
    from pathlib import Path

    stem = Path(filename).stem
    return (LLAMAINDEX_STORE_DIR / stem / "index_store.json").exists()


def _build_matches_from_raw_results(
    raw_results: list[dict],
    normalized_query: str,
    fallback_filename: str,
    *,
    corpus_bonus: float = 0.0,
) -> list[RetrievedChunkMatch]:
    matches: list[RetrievedChunkMatch] = []

    for result in raw_results:
        metadata = result["metadata"]
        source_filename = metadata.get("source_filename", fallback_filename)
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
                source_filename=source_filename,
                source_suffix=metadata.get("source_suffix", ""),
                document_kind=metadata.get(
                    "document_kind",
                    infer_document_kind(source_filename),
                ),
                corpus_document_id=_build_corpus_document_id(source_filename),
                corpus_node_id=_build_corpus_node_id(source_filename, result["chunk_id"]),
                char_count=metadata.get("char_count", len(result["content"])),
                section_title=metadata.get("section_title", ""),
                section_path=metadata.get("section_path", []),
                heading_level=metadata.get("heading_level"),
                content=result["content"],
                vector_score=result["score"],
                rerank_bonus=rerank_bonus,
                corpus_bonus=corpus_bonus,
                score=round(result["score"] + rerank_bonus + corpus_bonus, 6),
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


def _select_corpus_filenames(
    normalized_query: str,
    filenames: list[str],
) -> list[str]:
    """Lightweight metadata-aware filtering using query hints and filename semantics."""
    if not filenames:
        return []

    selected: list[str] = []
    lowered_query = normalized_query.lower()

    for filename in filenames:
        document_kind = infer_document_kind(filename)
        if any(
            hint in lowered_query and key == document_kind
            for key, hints in CORPUS_QUERY_HINTS.items()
            for hint in hints
        ):
            selected.append(filename)

    if selected:
        # Preserve original order while removing duplicates.
        return list(dict.fromkeys(selected))

    return filenames


def _tokenize_filename_terms(filename: str) -> set[str]:
    stem = filename.rsplit(".", 1)[0]
    return {token for token in stem.lower().replace("-", "_").split("_") if len(token) > 2}


def _matching_query_hints(normalized_query: str) -> set[str]:
    lowered_query = normalized_query.lower()
    matched_kinds: set[str] = set()

    for document_kind, hints in CORPUS_QUERY_HINTS.items():
        if any(hint in lowered_query for hint in hints):
            matched_kinds.add(document_kind)

    return matched_kinds


def _compute_corpus_document_bonus(
    filename: str,
    normalized_query: str,
    raw_results: list[dict],
) -> float:
    if not raw_results:
        return 0.0

    matched_kinds = _matching_query_hints(normalized_query)
    document_kind = infer_document_kind(filename)
    filename_terms = _tokenize_filename_terms(filename)
    query_terms = set(normalized_query.lower().replace("-", " ").split())
    max_vector_score = max(float(result["score"]) for result in raw_results)

    bonus = min(max_vector_score * 0.04, CORPUS_DOCUMENT_SCORE_BONUS_CAP)

    if document_kind in matched_kinds:
        bonus += CORPUS_KIND_MATCH_BONUS

    filename_overlap = len(filename_terms & query_terms)
    if filename_overlap:
        bonus += min(filename_overlap * CORPUS_FILENAME_MATCH_BONUS, 0.024)

    return round(bonus, 6)


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
    scoped_filenames = _select_corpus_filenames(normalized_query, ready_filenames)
    all_matches: list[RetrievedChunkMatch] = []

    for filename in scoped_filenames:
        raw_results = query_llamaindex_index(filename, normalized_query, top_k=top_k)
        corpus_bonus = _compute_corpus_document_bonus(
            filename=filename,
            normalized_query=normalized_query,
            raw_results=raw_results,
        )
        all_matches.extend(
            _build_matches_from_raw_results(
                raw_results=raw_results,
                normalized_query=normalized_query,
                fallback_filename=filename,
                corpus_bonus=corpus_bonus,
            )
        )

    all_matches.sort(key=lambda match: match.score, reverse=True)
    selected_matches = _select_diversified_corpus_matches(all_matches, top_k=top_k)
    latency_ms = round((perf_counter() - started) * 1000, 3)

    return RetrievalResult(
        filename=None,
        retrieval_scope="corpus",
        corpus_filenames=scoped_filenames,
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
