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
from app.services.ingestion.document_service import build_utc_timestamp
from app.services.ingestion.llamaindex_ingestion_service import (
    LLAMAINDEX_STORE_DIR,
    query_llamaindex_index,
)
from app.services.retrieval.retrieval_service import (
    compute_rerank_bonus,
    normalize_query_text,
)

logger = logging.getLogger(__name__)


def _index_exists(filename: str) -> bool:
    """Return True if a persisted LlamaIndex index exists for this document."""
    from pathlib import Path
    stem = Path(filename).stem
    return (LLAMAINDEX_STORE_DIR / stem / "index_store.json").exists()


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

    matches = []
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
                source_filename=metadata.get("source_filename", filename),
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

    return RetrievalResult(
        filename=filename,
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
