"""
Tests for the LlamaIndex ingestion service.
Uses mock chunks so no real documents or embeddings are required.
"""

import pytest

from app.services.ingestion.llamaindex_ingestion_service import (
    build_llamaindex_index,
    query_llamaindex_index,
)

MOCK_CHUNKS = {
    "filename": "test_doc.txt",
    "chunks": [
        {
            "chunk_id": "test_doc.txt::chunk_0",
            "chunk_index": 0,
            "source_filename": "test_doc.txt",
            "char_count": 40,
            "content": "LangGraph is a framework for building agents.",
        },
        {
            "chunk_id": "test_doc.txt::chunk_1",
            "chunk_index": 1,
            "source_filename": "test_doc.txt",
            "char_count": 38,
            "content": "LlamaIndex handles RAG and data indexing.",
        },
        {
            "chunk_id": "test_doc.txt::chunk_2",
            "chunk_index": 2,
            "source_filename": "test_doc.txt",
            "char_count": 35,
            "content": "Postgres stores checkpoints and state.",
        },
    ],
}


@pytest.fixture
def mock_chunks(workspace_tmp_path, monkeypatch):
    """Patch load_persisted_chunks and redirect store to workspace_tmp_path."""
    monkeypatch.setattr(
        "app.services.ingestion.llamaindex_ingestion_service.load_persisted_chunks",
        lambda _: MOCK_CHUNKS,
    )
    monkeypatch.setattr(
        "app.services.ingestion.llamaindex_ingestion_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    yield workspace_tmp_path


def test_build_llamaindex_index_returns_summary(mock_chunks):
    result = build_llamaindex_index("test_doc.txt")
    assert result["filename"] == "test_doc.txt"
    assert result["node_count"] == 3
    assert "store_path" in result


def test_build_llamaindex_index_persists_files(mock_chunks):
    build_llamaindex_index("test_doc.txt")
    store_dir = mock_chunks / "test_doc"
    assert (store_dir / "default__vector_store.json").exists()
    assert (store_dir / "docstore.json").exists()
    assert (store_dir / "index_store.json").exists()


def test_query_llamaindex_index_returns_ranked_results(mock_chunks):
    build_llamaindex_index("test_doc.txt")
    results = query_llamaindex_index("test_doc.txt", "agent framework", top_k=2)
    assert len(results) == 2
    assert all("chunk_id" in r and "content" in r and "score" in r for r in results)


def test_query_llamaindex_index_top_k_respected(mock_chunks):
    build_llamaindex_index("test_doc.txt")
    results = query_llamaindex_index("test_doc.txt", "database", top_k=1)
    assert len(results) == 1


def test_build_llamaindex_index_empty_chunks_raises(monkeypatch, workspace_tmp_path):
    monkeypatch.setattr(
        "app.services.ingestion.llamaindex_ingestion_service.load_persisted_chunks",
        lambda _: {"filename": "empty.txt", "chunks": []},
    )
    monkeypatch.setattr(
        "app.services.ingestion.llamaindex_ingestion_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    with pytest.raises(ValueError, match="no_chunks_found"):
        build_llamaindex_index("empty.txt")
