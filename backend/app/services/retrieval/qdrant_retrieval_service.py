"""Qdrant-backed retrieval service."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.schemas.indexing import PersistedEmbeddingDocument
from app.schemas.query import RetrievalResult, RetrievedChunkMatch
from app.services.indexing.embedding_service import (
    generate_query_embedding,
    load_persisted_embeddings,
)
from app.services.ingestion.document_service import (
    build_utc_timestamp,
    infer_document_kind,
    list_documents,
)
from app.services.retrieval.llamaindex_retrieval_service import (
    _build_corpus_document_id,
    _build_corpus_node_id,
    _compute_corpus_document_bonus,
    _select_corpus_filenames,
    _select_diversified_corpus_matches,
)
from app.services.retrieval.retrieval_service import (
    compute_rerank_bonus,
    normalize_query_text,
)
from app.storage.vector.qdrant_client import (
    _import_qdrant_client,
    build_qdrant_client,
    get_qdrant_collection_name,
    qdrant_enabled,
)


def _list_qdrant_candidate_documents() -> list[str]:
    return [
        item["filename"]
        for item in list_documents()
        if item.get("knowledge_assets", {}).get("embeddings_ready")
    ]


def _load_embedding_metadata(filename: str) -> PersistedEmbeddingDocument:
    return PersistedEmbeddingDocument.model_validate(load_persisted_embeddings(filename))


def _query_qdrant_points(
    query_vector: list[float],
    *,
    source_filename: str,
    limit: int,
) -> list[dict[str, Any]]:
    client = build_qdrant_client()
    if client is None:
        raise FileNotFoundError("qdrant")

    _, rest = _import_qdrant_client()
    results = client.search(
        collection_name=get_qdrant_collection_name(),
        query_vector=query_vector,
        query_filter=rest.Filter(
            must=[
                rest.FieldCondition(
                    key="source_filename",
                    match=rest.MatchValue(value=source_filename),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    raw_results: list[dict[str, Any]] = []
    for point in results:
        payload = point.payload or {}
        raw_results.append(
            {
                "chunk_id": payload.get("chunk_id", str(point.id)),
                "content": payload.get("content", ""),
                "score": round(float(point.score or 0.0), 6),
                "metadata": {
                    "chunk_index": payload.get("chunk_index", 0),
                    "source_filename": payload.get("source_filename", source_filename),
                    "source_suffix": payload.get("source_suffix", ""),
                    "document_kind": payload.get(
                        "document_kind",
                        infer_document_kind(source_filename),
                    ),
                    "char_count": payload.get("char_count", len(payload.get("content", ""))),
                    "section_title": payload.get("section_title", ""),
                    "section_path": payload.get("section_path", []),
                    "heading_level": payload.get("heading_level"),
                },
            }
        )

    return raw_results


def _build_matches_from_raw_results(
    raw_results: list[dict[str, Any]],
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


def retrieve_with_qdrant(
    filename: str,
    query_text: str,
    top_k: int = 3,
) -> RetrievalResult:
    """Retrieve document-scoped chunks from Qdrant."""
    if not qdrant_enabled():
        raise FileNotFoundError(filename)

    embedding_payload = _load_embedding_metadata(filename)
    started = perf_counter()
    normalized_query = normalize_query_text(query_text)
    (
        query_embedding_provider,
        query_embedding_model,
        query_vector,
    ) = generate_query_embedding(
        normalized_query,
        embedding_provider=embedding_payload.embedding_provider,
        embedding_model=embedding_payload.embedding_model,
        vector_dim=embedding_payload.vector_dim,
    )
    raw_results = _query_qdrant_points(
        query_vector,
        source_filename=filename,
        limit=top_k,
    )
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
        embedding_provider="qdrant",
        embedding_model=embedding_payload.embedding_model,
        vector_dim=embedding_payload.vector_dim,
        question=query_text,
        top_k=top_k,
        retrieved_at=build_utc_timestamp(),
        retrieval_latency_ms=latency_ms,
        query_embedding_provider=query_embedding_provider,
        query_embedding_model=query_embedding_model,
        matches=matches,
    )


def retrieve_with_qdrant_corpus(
    query_text: str,
    top_k: int = 3,
    filenames: list[str] | None = None,
) -> RetrievalResult:
    """Retrieve and merge corpus-scoped chunks from Qdrant."""
    if not qdrant_enabled():
        raise FileNotFoundError("qdrant_corpus")

    candidate_filenames = filenames or _list_qdrant_candidate_documents()
    if not candidate_filenames:
        raise FileNotFoundError("qdrant_corpus")

    ready_filenames: list[str] = []
    embedding_documents: dict[str, PersistedEmbeddingDocument] = {}
    for filename in candidate_filenames:
        try:
            embedding_payload = _load_embedding_metadata(filename)
        except FileNotFoundError:
            continue
        ready_filenames.append(filename)
        embedding_documents[filename] = embedding_payload

    if not ready_filenames:
        raise FileNotFoundError("qdrant_corpus")

    started = perf_counter()
    normalized_query = normalize_query_text(query_text)
    scoped_filenames = _select_corpus_filenames(normalized_query, ready_filenames)
    sample_payload = embedding_documents[scoped_filenames[0]]
    (
        query_embedding_provider,
        query_embedding_model,
        query_vector,
    ) = generate_query_embedding(
        normalized_query,
        embedding_provider=sample_payload.embedding_provider,
        embedding_model=sample_payload.embedding_model,
        vector_dim=sample_payload.vector_dim,
    )

    all_matches: list[RetrievedChunkMatch] = []
    for filename in scoped_filenames:
        raw_results = _query_qdrant_points(
            query_vector,
            source_filename=filename,
            limit=top_k,
        )
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
        embedding_provider="qdrant",
        embedding_model=sample_payload.embedding_model,
        vector_dim=sample_payload.vector_dim,
        question=query_text,
        top_k=top_k,
        retrieved_at=build_utc_timestamp(),
        retrieval_latency_ms=latency_ms,
        query_embedding_provider=query_embedding_provider,
        query_embedding_model=query_embedding_model,
        matches=selected_matches,
    )
