import json
from types import SimpleNamespace
import uuid

import pytest

from app.core.config import settings
from app.services.indexing import embedding_service
from app.services.vectorstore import qdrant_index_service


def test_sync_document_embeddings_to_qdrant_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "")

    result = qdrant_index_service.sync_document_embeddings_to_qdrant("sample.txt")

    assert result["enabled"] is False
    assert result["synced"] is False
    assert result["reason"] == "qdrant_not_configured"


def test_sync_document_embeddings_to_qdrant_upserts_points(workspace_tmp_path, monkeypatch):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()
    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")

    payload = {
        "filename": "sample.txt",
        "suffix": ".txt",
        "embedding_provider": "mock",
        "embedding_model": "mock-embedding-v1",
        "vector_dim": 8,
        "source_path": "../data/raw/sample.txt",
        "source_chunk_path": "../data/chunks/sample.chunks.json",
        "created_at": "2026-03-14T00:00:00+00:00",
        "pipeline_version": "indexing-v1",
        "chunk_count": 2,
        "embeddings": [
            {
                "embedding_id": "sample.txt::chunk_0::embedding",
                "chunk_id": "sample.txt::chunk_0",
                "chunk_index": 0,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "document_kind": "reference",
                "char_count": 5,
                "section_title": "",
                "section_path": [],
                "heading_level": None,
                "content": "hello",
                "vector": [0.1] * 8,
            },
            {
                "embedding_id": "sample.txt::chunk_1::embedding",
                "chunk_id": "sample.txt::chunk_1",
                "chunk_index": 1,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "document_kind": "reference",
                "char_count": 5,
                "section_title": "",
                "section_path": [],
                "heading_level": None,
                "content": "world",
                "vector": [0.2] * 8,
            },
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(json.dumps(payload), encoding="utf-8")

    operations = {}

    class DummyClient:
        def delete(self, **kwargs):
            operations["delete"] = kwargs

        def upsert(self, **kwargs):
            operations["upsert"] = kwargs

    rest = SimpleNamespace(
        FilterSelector=lambda **kwargs: SimpleNamespace(**kwargs),
        Filter=lambda **kwargs: SimpleNamespace(**kwargs),
        FieldCondition=lambda **kwargs: SimpleNamespace(**kwargs),
        MatchValue=lambda **kwargs: SimpleNamespace(**kwargs),
        PointStruct=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    monkeypatch.setattr(
        qdrant_index_service,
        "build_qdrant_client",
        lambda: DummyClient(),
    )
    monkeypatch.setattr(
        qdrant_index_service,
        "_import_qdrant_client",
        lambda: (object, rest),
    )
    monkeypatch.setattr(
        qdrant_index_service,
        "ensure_qdrant_collection",
        lambda vector_dim: {
            "collection_name": "agent_knowledge_chunks",
            "created": True,
            "vector_dim": vector_dim,
        },
    )

    result = qdrant_index_service.sync_document_embeddings_to_qdrant("sample.txt")

    assert result["synced"] is True
    assert result["point_count"] == 2
    assert operations["delete"]["collection_name"] == "agent_knowledge_chunks"
    assert operations["upsert"]["collection_name"] == "agent_knowledge_chunks"
    assert operations["upsert"]["wait"] is True
    assert len(operations["upsert"]["points"]) == 2
    assert str(uuid.UUID(operations["upsert"]["points"][0].id)) == operations["upsert"]["points"][0].id


def test_sync_document_embeddings_to_qdrant_rejects_zero_dim(workspace_tmp_path, monkeypatch):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()
    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")

    payload = {
        "filename": "sample.txt",
        "suffix": ".txt",
        "embedding_provider": "mock",
        "embedding_model": "mock-embedding-v1",
        "vector_dim": 0,
        "source_path": "../data/raw/sample.txt",
        "source_chunk_path": "../data/chunks/sample.chunks.json",
        "created_at": "2026-03-14T00:00:00+00:00",
        "pipeline_version": "indexing-v1",
        "chunk_count": 0,
        "embeddings": [],
    }
    (embedding_dir / "sample.embeddings.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="qdrant_vector_dim_invalid"):
        qdrant_index_service.sync_document_embeddings_to_qdrant("sample.txt")
