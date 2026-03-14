import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.indexing import embedding_service
from app.services.retrieval.retrieval_service import compute_rerank_bonus


def test_query_endpoint_returns_fallback_answer_with_retrieval_results(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")

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
    assert payload["answered_at"]
    assert payload["answer_latency_ms"] >= 0
    assert payload["chat_provider"] == "fallback"
    assert payload["chat_model"] == "local-fallback"
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
    assert payload["retrieval"]["matches"][0]["score"] >= payload["retrieval"]["matches"][0]["vector_score"]


def test_query_diagnostics_endpoint_returns_ranked_candidates(
    workspace_tmp_path,
    monkeypatch,
):
    embedding_dir = workspace_tmp_path / "embeddings"
    embedding_dir.mkdir()

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    monkeypatch.setattr(settings, "chat_provider", "fallback")

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
        "chunk_count": 3,
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
            {
                "embedding_id": "sample.txt::chunk_2::embedding",
                "chunk_id": "sample.txt::chunk_2",
                "chunk_index": 2,
                "source_filename": "sample.txt",
                "source_suffix": ".txt",
                "char_count": 12,
                "content": "agent system",
                "vector": embedding_service.build_mock_embedding("agent system"),
            },
        ],
    }
    (embedding_dir / "sample.embeddings.json").write_text(
        json.dumps(embedding_payload),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/query/diagnostics",
        json={
            "filename": "sample.txt",
            "question": "rag systems",
            "top_k": 2,
            "candidate_count": 3,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["filename"] == "sample.txt"
    assert payload["retrieval"]["top_k"] == 2
    assert len(payload["retrieval"]["matches"]) == 2
    assert len(payload["candidates"]) == 3
    assert payload["candidates"][0]["chunk_id"] == "sample.txt::chunk_0"
    assert payload["candidates"][0]["score"] >= payload["candidates"][0]["vector_score"]
    assert payload["diagnostics"]["returned_candidate_count"] == 3
    assert payload["diagnostics"]["total_scored_chunks"] == 3
    assert payload["diagnostics"]["max_score"] >= payload["diagnostics"]["min_score"]


def test_definition_query_gets_higher_bonus_for_definition_chunk():
    definition_chunk = (
        "# Retrieval-Augmented Generation Overview\n\n"
        "## What RAG Means\n\n"
        "Retrieval-augmented generation, or RAG, is a system pattern."
    )
    generic_chunk = (
        "An enterprise agent system can use RAG as a knowledge layer "
        "for retrieval and tool use."
    )

    definition_bonus = compute_rerank_bonus("What is RAG?", definition_chunk)
    generic_bonus = compute_rerank_bonus("What is RAG?", generic_chunk)

    assert definition_bonus > generic_bonus
