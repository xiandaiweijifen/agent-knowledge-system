import json

import httpx

from app.core.config import settings
from app.services.indexing import embedding_service
from app.services.ingestion import document_service


def test_persist_document_embeddings_creates_embedding_artifact(
    workspace_tmp_path,
    monkeypatch,
):
    chunk_dir = workspace_tmp_path / "chunks"
    embedding_dir = workspace_tmp_path / "embeddings"
    chunk_dir.mkdir()
    embedding_dir.mkdir()

    monkeypatch.setattr(document_service, "CHUNK_DATA_DIR", chunk_dir)
    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "embedding_provider", "mock")

    chunk_payload = {
        "filename": "sample.txt",
        "suffix": ".txt",
        "size_bytes": 42,
        "source_path": "../data/raw/sample.txt",
        "created_at": "2026-03-14T00:00:00+00:00",
        "pipeline_version": "ingestion-v1",
        "chunk_strategy": "character",
        "chunk_count": 2,
        "chunk_size": 500,
        "chunk_overlap": 100,
        "chunks": [
            {
                "chunk_id": "sample.txt::chunk_0",
                "chunk_index": 0,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "start_char": 0,
                "end_char": 5,
                "char_count": 5,
                "content": "hello",
            },
            {
                "chunk_id": "sample.txt::chunk_1",
                "chunk_index": 1,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "start_char": 6,
                "end_char": 11,
                "char_count": 5,
                "content": "world",
            },
        ],
    }
    (chunk_dir / "sample.chunks.json").write_text(
        json.dumps(chunk_payload),
        encoding="utf-8",
    )

    result = embedding_service.persist_document_embeddings("sample.txt")
    persisted_payload = embedding_service.load_persisted_embeddings("sample.txt")

    assert result["filename"] == "sample.txt"
    assert result["embedding_provider"] == "mock"
    assert result["embedding_model"] == "mock-embedding-v1"
    assert result["vector_dim"] == 8
    assert result["embedding_count"] == 2
    assert result["pipeline_version"] == "indexing-v1"
    assert result["created_at"]

    assert persisted_payload["filename"] == "sample.txt"
    assert persisted_payload["source_path"] == "../data/raw/sample.txt"
    assert persisted_payload["source_chunk_path"].endswith("sample.chunks.json")
    assert persisted_payload["pipeline_version"] == "indexing-v1"
    assert persisted_payload["embedding_provider"] == "mock"
    assert persisted_payload["created_at"]
    assert persisted_payload["chunk_count"] == 2
    assert len(persisted_payload["embeddings"]) == 2
    assert len(persisted_payload["embeddings"][0]["vector"]) == 8


def test_build_mock_embedding_supports_large_vector_dimensions():
    vector = embedding_service.build_mock_embedding("rag systems", vector_dim=3072)

    assert len(vector) == 3072


def test_persist_document_embeddings_surfaces_provider_fallback_reason(
    workspace_tmp_path,
    monkeypatch,
):
    chunk_dir = workspace_tmp_path / "chunks"
    embedding_dir = workspace_tmp_path / "embeddings"
    chunk_dir.mkdir()
    embedding_dir.mkdir()

    monkeypatch.setattr(document_service, "CHUNK_DATA_DIR", chunk_dir)
    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "embedding_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "configured")
    monkeypatch.setattr(
        embedding_service,
        "build_gemini_embeddings",
        lambda texts, model_name=None: (_ for _ in ()).throw(ValueError("bad_response_shape")),
    )

    chunk_payload = {
        "filename": "sample.txt",
        "suffix": ".txt",
        "size_bytes": 42,
        "source_path": "../data/raw/sample.txt",
        "created_at": "2026-03-14T00:00:00+00:00",
        "pipeline_version": "ingestion-v1",
        "chunk_strategy": "character",
        "chunk_count": 1,
        "chunk_size": 500,
        "chunk_overlap": 100,
        "chunks": [
            {
                "chunk_id": "sample.txt::chunk_0",
                "chunk_index": 0,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "start_char": 0,
                "end_char": 5,
                "char_count": 5,
                "content": "hello",
            }
        ],
    }
    (chunk_dir / "sample.chunks.json").write_text(
        json.dumps(chunk_payload),
        encoding="utf-8",
    )

    result = embedding_service.persist_document_embeddings("sample.txt")

    assert result["embedding_provider"] == "mock_fallback"
    assert "embedding_warning" in result
    assert "ValueError: bad_response_shape" in result["embedding_warning"]


def test_build_gemini_embeddings_uses_configured_proxy_and_short_connect_timeout(monkeypatch):
    captured: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [{"values": [0.1, 0.2, 0.3]}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["trust_env"] = kwargs.get("trust_env")
        captured["timeout"] = kwargs.get("timeout")
        return DummyResponse()

    monkeypatch.setattr(settings, "gemini_api_key", "configured")
    monkeypatch.setattr(settings, "gemini_embedding_model", "gemini-embedding-001")
    monkeypatch.setattr(settings, "embedding_http_trust_env", True)
    monkeypatch.setattr(embedding_service.httpx, "post", fake_post)

    model, vectors = embedding_service.build_gemini_embeddings(["hello"])

    assert model == "gemini-embedding-001"
    assert vectors == [[0.1, 0.2, 0.3]]
    assert captured["trust_env"] is True
    assert isinstance(captured["timeout"], httpx.Timeout)
    assert captured["timeout"].connect == 5.0
    assert captured["timeout"].read == 30.0
