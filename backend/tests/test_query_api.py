import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.indexing import embedding_service


def test_query_endpoint_returns_fallback_answer_with_retrieval_results(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)

    embedding_payload = {
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
                "char_count": 11,
                "content": "rag systems",
                "vector": embedding_service.build_mock_embedding("rag systems"),
            },
            {
                "embedding_id": "sample.txt::chunk_1::embedding",
                "chunk_id": "sample.txt::chunk_1",
                "chunk_index": 1,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 10,
                "content": "data lake",
                "vector": embedding_service.build_mock_embedding("data lake"),
            },
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(
        json.dumps(embedding_payload),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/query",
        json={
            "filename": "sample.txt",
            "question": "rag systems",
            "top_k": 1,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["filename"] == "sample.txt"
    assert payload["answer_source"] == "fallback"
    assert payload["model"] == "local-fallback"
    assert payload["retrieval"]["top_k"] == 1
    assert payload["retrieval"]["embedding_provider"] == "mock"
    assert payload["retrieval"]["embedding_model"] == "mock-embedding-v1"
    assert payload["retrieval"]["vector_dim"] == 8
    assert payload["retrieval"]["query_embedding_provider"] == "mock"
    assert payload["retrieval"]["query_embedding_model"] == "mock-embedding-v1"
    assert payload["retrieval"]["retrieved_at"]
    assert payload["retrieval"]["retrieval_latency_ms"] >= 0
    assert len(payload["retrieval"]["matches"]) == 1
    assert payload["retrieval"]["matches"][0]["chunk_id"] == "sample.txt::chunk_0"
