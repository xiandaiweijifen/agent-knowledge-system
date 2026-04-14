"""
Vector index service.

This package-level adapter isolates the rest of the codebase from the
current LlamaIndex-backed implementation so future providers such as
Qdrant can be introduced behind the same surface.
"""

from __future__ import annotations

from typing import Any

from app.services.ingestion.llamaindex_ingestion_service import (
    build_llamaindex_index,
    has_llamaindex_index,
)


def build_vector_index(filename: str) -> dict[str, Any]:
    """Build the project's active vector index for a document."""
    return build_llamaindex_index(filename)


def has_vector_index(filename: str) -> bool:
    """Return whether the project's active vector index exists for a document."""
    return has_llamaindex_index(filename)

