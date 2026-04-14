"""
Vector store retrieval service.

This adapter preserves the existing RetrievalResult contract while routing
knowledge retrieval through the currently active vector index backend.
"""

from __future__ import annotations

from app.schemas.query import RetrievalResult
from app.services.retrieval.llamaindex_retrieval_service import (
    retrieve_with_llamaindex,
    retrieve_with_llamaindex_corpus,
)


def retrieve_with_vector_index(
    filename: str,
    query_text: str,
    top_k: int = 3,
) -> RetrievalResult:
    """Retrieve document-scoped matches from the active vector index."""
    return retrieve_with_llamaindex(
        filename=filename,
        query_text=query_text,
        top_k=top_k,
    )


def retrieve_with_vector_index_corpus(
    query_text: str,
    top_k: int = 3,
    filenames: list[str] | None = None,
) -> RetrievalResult:
    """Retrieve corpus-scoped matches from the active vector index."""
    return retrieve_with_llamaindex_corpus(
        query_text=query_text,
        top_k=top_k,
        filenames=filenames,
    )

