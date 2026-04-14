"""Qdrant write-path helpers for document embedding synchronization."""

from __future__ import annotations

from typing import Any

from app.schemas.indexing import PersistedEmbeddingDocument
from app.services.indexing.embedding_service import load_persisted_embeddings
from app.storage.vector.qdrant_client import (
    _import_qdrant_client,
    build_qdrant_client,
    build_qdrant_payload,
    build_qdrant_point_id,
    ensure_qdrant_collection,
    get_qdrant_collection_name,
    qdrant_enabled,
)


def sync_document_embeddings_to_qdrant(filename: str) -> dict[str, Any]:
    """
    Synchronize a document's persisted embeddings into Qdrant.

    The function is intentionally tolerant of Qdrant being unconfigured so
    the existing local-first flow remains unchanged unless the caller opts in.
    """
    if not qdrant_enabled():
        return {
            "enabled": False,
            "synced": False,
            "reason": "qdrant_not_configured",
        }

    embedding_payload = PersistedEmbeddingDocument.model_validate(
        load_persisted_embeddings(filename)
    )
    if embedding_payload.vector_dim <= 0:
        raise ValueError("qdrant_vector_dim_invalid")

    client = build_qdrant_client()
    if client is None:
        return {
            "enabled": False,
            "synced": False,
            "reason": "qdrant_not_configured",
        }

    _, rest = _import_qdrant_client()
    collection_summary = ensure_qdrant_collection(embedding_payload.vector_dim)
    collection_name = get_qdrant_collection_name()

    client.delete(
        collection_name=collection_name,
        points_selector=rest.FilterSelector(
            filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="source_filename",
                        match=rest.MatchValue(value=embedding_payload.filename),
                    )
                ]
            )
        ),
    )

    points = [
        rest.PointStruct(
            id=build_qdrant_point_id(embedding.chunk_id),
            vector=embedding.vector,
            payload=build_qdrant_payload(
                filename=embedding_payload.filename,
                embedding_record=embedding,
            ),
        )
        for embedding in embedding_payload.embeddings
    ]

    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )

    return {
        "enabled": True,
        "synced": True,
        "collection_name": collection_summary["collection_name"],
        "collection_created": collection_summary["created"],
        "vector_dim": collection_summary["vector_dim"],
        "point_count": len(points),
        "filename": embedding_payload.filename,
    }
