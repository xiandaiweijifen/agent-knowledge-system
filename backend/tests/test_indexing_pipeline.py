import json

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
