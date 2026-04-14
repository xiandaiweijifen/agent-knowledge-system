"""
Qdrant client setup and collection conventions.

This module is intentionally side-effect free at import time so the
project can run without Qdrant installed or configured until the
integration is explicitly enabled.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

QDRANT_PAYLOAD_TEXT_FIELDS = ("content", "section_title", "source_filename", "document_kind")


def qdrant_enabled() -> bool:
    """Return whether Qdrant has enough configuration to be usable."""
    return bool(settings.qdrant_url or settings.qdrant_local_path)


def get_qdrant_collection_name() -> str:
    """Return a normalized collection name for the active project."""
    normalized = settings.qdrant_collection_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = normalized.strip("_-")
    return normalized or "agent_knowledge_chunks"


def _import_qdrant_client():
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as rest
    except ImportError as exc:
        raise RuntimeError("qdrant_client_not_installed") from exc

    return QdrantClient, rest


def build_qdrant_client() -> Any | None:
    """
    Build a Qdrant client from project settings.

    Returns None when Qdrant is not configured. Raises RuntimeError when
    Qdrant is configured but the dependency is unavailable.
    """
    if not qdrant_enabled():
        logger.info("Qdrant not configured")
        return None

    QdrantClient, _ = _import_qdrant_client()

    if settings.qdrant_local_path:
        logger.info("Using local Qdrant path at %s", settings.qdrant_local_path)
        return QdrantClient(path=settings.qdrant_local_path)

    logger.info("Using remote Qdrant endpoint at %s", settings.qdrant_url)
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        prefer_grpc=settings.qdrant_prefer_grpc,
    )


def ensure_qdrant_collection(vector_dim: int, distance: str = "Cosine") -> dict[str, Any]:
    """
    Ensure the configured collection exists with the requested vector size.

    This helper is idempotent for matching collections and raises when an
    existing collection uses a different vector size.
    """
    client = build_qdrant_client()
    if client is None:
        raise RuntimeError("qdrant_not_configured")

    _, rest = _import_qdrant_client()
    collection_name = get_qdrant_collection_name()
    existing_collections = {
        collection.name for collection in client.get_collections().collections
    }

    if collection_name not in existing_collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=rest.VectorParams(
                size=vector_dim,
                distance=getattr(rest.Distance, distance.upper()),
            ),
        )
        for field_name in QDRANT_PAYLOAD_TEXT_FIELDS:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=rest.PayloadSchemaType.KEYWORD
                if field_name != "content"
                else rest.PayloadSchemaType.TEXT,
            )
        return {
            "collection_name": collection_name,
            "created": True,
            "vector_dim": vector_dim,
        }

    collection_info = client.get_collection(collection_name=collection_name)
    existing_vector_dim = collection_info.config.params.vectors.size
    if existing_vector_dim != vector_dim:
        raise ValueError("qdrant_vector_dim_mismatch")

    return {
        "collection_name": collection_name,
        "created": False,
        "vector_dim": existing_vector_dim,
    }


def build_qdrant_point_id(chunk_id: str) -> str:
    """Return a stable Qdrant point id derived from the chunk id."""
    return chunk_id


def build_qdrant_payload(*, filename: str, embedding_record: Any) -> dict[str, Any]:
    """Build a normalized Qdrant payload from an embedding-like record."""
    return {
        "chunk_id": embedding_record.chunk_id,
        "chunk_index": embedding_record.chunk_index,
        "source_filename": embedding_record.source_filename,
        "source_suffix": embedding_record.source_suffix,
        "document_kind": embedding_record.document_kind,
        "char_count": embedding_record.char_count,
        "section_title": embedding_record.section_title,
        "section_path": list(embedding_record.section_path),
        "heading_level": embedding_record.heading_level,
        "content": embedding_record.content,
        "corpus_document_id": filename.strip().lower(),
    }
