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
    raw_results = query_llamaindex_index(filename, query_text, top_k=top_k)
    latency_ms = round((perf_counter() - started) * 1000, 3)

    matches = [
        RetrievedChunkMatch(
            chunk_id=r["chunk_id"],
            chunk_index=r["metadata"].get("chunk_index", 0),
            source_filename=r["metadata"].get("source_filename", filename),
            source_suffix=r["metadata"].get("source_suffix", ""),
            char_count=r["metadata"].get("char_count", len(r["content"])),
            content=r["content"],
            vector_score=r["score"],
            rerank_bonus=0.0,
            score=r["score"],
        )
        for r in raw_results
    ]

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
