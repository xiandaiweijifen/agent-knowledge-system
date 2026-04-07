"""
Tests for the LlamaIndex retrieval service and query_service fallback logic.
"""

import pytest
from unittest.mock import MagicMock

from app.services.retrieval.llamaindex_retrieval_service import (
    retrieve_with_llamaindex,
    _index_exists,
)


def test_index_exists_returns_false_when_missing(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    assert _index_exists("nonexistent.txt") is False


def test_index_exists_returns_true_when_present(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    index_dir = workspace_tmp_path / "mydoc"
    index_dir.mkdir()
    (index_dir / "index_store.json").write_text("{}")
    assert _index_exists("mydoc.txt") is True


def test_retrieve_with_llamaindex_raises_when_no_index(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    with pytest.raises(FileNotFoundError):
        retrieve_with_llamaindex("missing.txt", "what is this?")


def test_retrieve_with_llamaindex_returns_retrieval_result(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    # Fake an existing index
    index_dir = workspace_tmp_path / "mydoc"
    index_dir.mkdir()
    (index_dir / "index_store.json").write_text("{}")

    mock_results = [
        {
            "chunk_id": "mydoc.txt::chunk_0",
            "content": "LangGraph builds agents.",
            "score": 0.87,
            "metadata": {"chunk_index": 0, "source_filename": "mydoc.txt", "char_count": 26},
        }
    ]
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.query_llamaindex_index",
        MagicMock(return_value=mock_results),
    )

    result = retrieve_with_llamaindex("mydoc.txt", "agent framework", top_k=1)

    assert result.filename == "mydoc.txt"
    assert result.embedding_provider == "llamaindex"
    assert len(result.matches) == 1
    assert result.matches[0].chunk_id == "mydoc.txt::chunk_0"
    assert result.matches[0].score == 0.87


def test_query_service_falls_back_to_legacy(monkeypatch):
    """query_service.run_query falls back to legacy when no LlamaIndex index exists."""
    from app.services.agent.query_service import run_query
    from app.schemas.query import RetrievalResult

    legacy_result = RetrievalResult(
        filename="doc.txt",
        embedding_provider="mock",
        embedding_model="mock-v1",
        vector_dim=8,
        question="test question",
        top_k=3,
        retrieved_at="2024-01-01T00:00:00Z",
        retrieval_latency_ms=1.0,
        query_embedding_provider="mock",
        query_embedding_model="mock-v1",
        matches=[],
    )

    monkeypatch.setattr(
        "app.services.agent.query_service.retrieve_with_llamaindex",
        MagicMock(side_effect=FileNotFoundError("doc.txt")),
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.retrieve_relevant_chunks",
        MagicMock(return_value=legacy_result),
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.generate_rag_answer",
        MagicMock(return_value={
            "answer": "test", "answer_source": "llm", "model": "mock",
            "answered_at": "2024-01-01", "answer_latency_ms": 1.0,
            "chat_provider": "mock", "chat_model": "mock",
        }),
    )

    result = run_query("doc.txt", "test question", top_k=3)
    assert result.filename == "doc.txt"
