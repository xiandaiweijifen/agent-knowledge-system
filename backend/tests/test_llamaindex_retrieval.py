"""
Tests for the LlamaIndex retrieval service and query_service fallback logic.
"""

import pytest
from unittest.mock import MagicMock

from app.services.retrieval.llamaindex_retrieval_service import (
    retrieve_with_llamaindex,
    retrieve_with_llamaindex_corpus,
    _index_exists,
    _select_corpus_filenames,
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
            "metadata": {
                "chunk_index": 0,
                "source_filename": "mydoc.txt",
                "char_count": 26,
                "section_title": "Agent Framework",
                "section_path": ["Agent Framework"],
                "heading_level": 2,
            },
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
    assert result.matches[0].section_title == "Agent Framework"
    assert result.matches[0].section_path == ["Agent Framework"]
    assert result.matches[0].heading_level == 2
    assert result.matches[0].score >= 0.87


def test_retrieve_with_llamaindex_uses_metadata_bonus_for_rerank(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    index_dir = workspace_tmp_path / "mydoc"
    index_dir.mkdir()
    (index_dir / "index_store.json").write_text("{}")

    mock_results = [
        {
            "chunk_id": "mydoc.txt::chunk_0",
            "content": "This chunk covers generic platform notes.",
            "score": 0.84,
            "metadata": {
                "chunk_index": 0,
                "source_filename": "mydoc.txt",
                "char_count": 33,
                "section_title": "Overview",
                "section_path": ["Overview"],
                "heading_level": 1,
            },
        },
        {
            "chunk_id": "mydoc.txt::chunk_1",
            "content": "This chunk also covers generic platform notes.",
            "score": 0.8,
            "metadata": {
                "chunk_index": 1,
                "source_filename": "mydoc.txt",
                "char_count": 38,
                "section_title": "Common Failure Modes",
                "section_path": ["Overview", "Common Failure Modes"],
                "heading_level": 2,
            },
        },
    ]
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.query_llamaindex_index",
        MagicMock(return_value=mock_results),
    )

    result = retrieve_with_llamaindex("mydoc.txt", "what are the common failure modes?", top_k=2)

    assert result.matches[0].chunk_id == "mydoc.txt::chunk_1"
    assert result.matches[0].rerank_bonus > 0.0


def test_retrieve_with_llamaindex_corpus_merges_multiple_documents(workspace_tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    for stem in ("doc_a", "doc_b"):
        index_dir = workspace_tmp_path / stem
        index_dir.mkdir()
        (index_dir / "index_store.json").write_text("{}")

    mock_results = {
        "doc_a.md": [
            {
                "chunk_id": "doc_a.md::chunk_0",
                "content": "Generic architecture notes.",
                "score": 0.82,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "doc_a.md",
                    "source_suffix": ".md",
                    "char_count": 27,
                    "section_title": "Overview",
                    "section_path": ["Overview"],
                    "heading_level": 1,
                },
            }
        ],
        "doc_b.md": [
            {
                "chunk_id": "doc_b.md::chunk_0",
                "content": "Common RAG failure modes include weak embeddings.",
                "score": 0.79,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "doc_b.md",
                    "source_suffix": ".md",
                    "char_count": 49,
                    "section_title": "Common Failure Modes",
                    "section_path": ["RAG", "Common Failure Modes"],
                    "heading_level": 2,
                },
            }
        ],
    }

    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.query_llamaindex_index",
        MagicMock(side_effect=lambda filename, query_text, top_k: mock_results[filename]),
    )

    result = retrieve_with_llamaindex_corpus(
        "please explain the common failure modes",
        top_k=2,
        filenames=["doc_a.md", "doc_b.md"],
    )

    assert result.filename is None
    assert result.retrieval_scope == "corpus"
    assert result.corpus_filenames == ["doc_a.md", "doc_b.md"]
    assert len(result.matches) == 2
    assert result.matches[0].source_filename == "doc_b.md"
    assert result.matches[0].section_title == "Common Failure Modes"


def test_retrieve_with_llamaindex_corpus_diversifies_near_tied_sources(
    workspace_tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    for stem in ("doc_a", "doc_b"):
        index_dir = workspace_tmp_path / stem
        index_dir.mkdir()
        (index_dir / "index_store.json").write_text("{}")

    mock_results = {
        "doc_a.md": [
            {
                "chunk_id": "doc_a.md::chunk_0",
                "content": "Common failure modes overview for system A.",
                "score": 0.91,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "doc_a.md",
                    "source_suffix": ".md",
                    "char_count": 42,
                    "section_title": "Common Failure Modes",
                    "section_path": ["Overview", "Common Failure Modes"],
                    "heading_level": 2,
                },
            },
            {
                "chunk_id": "doc_a.md::chunk_1",
                "content": "Common failure modes examples for system A.",
                "score": 0.9,
                "metadata": {
                    "chunk_index": 1,
                    "source_filename": "doc_a.md",
                    "source_suffix": ".md",
                    "char_count": 42,
                    "section_title": "Common Failure Modes",
                    "section_path": ["Overview", "Common Failure Modes"],
                    "heading_level": 2,
                },
            },
        ],
        "doc_b.md": [
            {
                "chunk_id": "doc_b.md::chunk_0",
                "content": "Common failure modes overview for system B.",
                "score": 0.89,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "doc_b.md",
                    "source_suffix": ".md",
                    "char_count": 42,
                    "section_title": "Common Failure Modes",
                    "section_path": ["RAG", "Common Failure Modes"],
                    "heading_level": 2,
                },
            }
        ],
    }

    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.query_llamaindex_index",
        MagicMock(side_effect=lambda filename, query_text, top_k: mock_results[filename]),
    )

    result = retrieve_with_llamaindex_corpus(
        "common failure modes",
        top_k=2,
        filenames=["doc_a.md", "doc_b.md"],
    )

    assert [match.source_filename for match in result.matches] == ["doc_a.md", "doc_b.md"]


def test_select_corpus_filenames_prefers_runbook_documents_for_runbook_queries():
    filenames = [
        "rag_overview.md",
        "checkout_service_runbook.md",
        "incident_playbook.md",
    ]

    selected = _select_corpus_filenames(
        "show the runbook for checkout recovery",
        filenames,
    )

    assert selected == ["checkout_service_runbook.md"]


def test_select_corpus_filenames_falls_back_to_all_documents_without_hints():
    filenames = [
        "rag_overview.md",
        "checkout_service_runbook.md",
        "incident_playbook.md",
    ]

    selected = _select_corpus_filenames(
        "summarize the available engineering notes",
        filenames,
    )

    assert selected == filenames


def test_retrieve_with_llamaindex_corpus_scopes_documents_from_query_hints(
    workspace_tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.LLAMAINDEX_STORE_DIR",
        workspace_tmp_path,
    )
    for stem in ("rag_overview", "checkout_service_runbook", "incident_playbook"):
        index_dir = workspace_tmp_path / stem
        index_dir.mkdir()
        (index_dir / "index_store.json").write_text("{}")

    query_mock = MagicMock(
        side_effect=lambda filename, query_text, top_k: [
            {
                "chunk_id": f"{filename}::chunk_0",
                "content": f"content for {filename}",
                "score": 0.8,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": filename,
                    "source_suffix": ".md",
                    "char_count": 20,
                    "section_title": "Overview",
                    "section_path": ["Overview"],
                    "heading_level": 1,
                },
            }
        ]
    )
    monkeypatch.setattr(
        "app.services.retrieval.llamaindex_retrieval_service.query_llamaindex_index",
        query_mock,
    )

    result = retrieve_with_llamaindex_corpus(
        "please show the runbook for checkout recovery",
        top_k=2,
        filenames=[
            "rag_overview.md",
            "checkout_service_runbook.md",
            "incident_playbook.md",
        ],
    )

    assert result.corpus_filenames == ["checkout_service_runbook.md"]
    assert query_mock.call_count == 1
    assert result.matches[0].source_filename == "checkout_service_runbook.md"


def test_query_service_falls_back_to_legacy_in_debug_context(monkeypatch):
    """query_service.run_query_with_context may fall back to legacy in debug mode."""
    from app.services.agent.query_service import run_query_with_context
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
        "app.services.agent.query_service.settings.knowledge_retrieval_mode",
        "auto",
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

    result = run_query_with_context(
        "doc.txt",
        "test question",
        top_k=3,
        execution_context="debug",
    )
    assert result.filename == "doc.txt"


def test_query_service_requires_llamaindex_by_default(monkeypatch):
    from app.services.agent.query_service import run_query

    monkeypatch.setattr(
        "app.services.agent.query_service.settings.knowledge_retrieval_mode",
        "llamaindex",
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.retrieve_with_llamaindex",
        MagicMock(side_effect=FileNotFoundError("doc.txt")),
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.retrieve_relevant_chunks",
        MagicMock(),
    )

    with pytest.raises(ValueError, match="llamaindex_index_not_found"):
        run_query("doc.txt", "test question", top_k=3)


def test_query_service_standard_context_rejects_legacy_mode(monkeypatch):
    from app.services.agent.query_service import run_query

    monkeypatch.setattr(
        "app.services.agent.query_service.settings.knowledge_retrieval_mode",
        "legacy",
    )

    with pytest.raises(ValueError, match="knowledge_retrieval_mode_requires_debug_or_eval"):
        run_query("doc.txt", "test question", top_k=3)


def test_query_service_legacy_mode_skips_llamaindex_in_eval_context(monkeypatch):
    from app.services.agent.query_service import run_query_with_context
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

    llamaindex_mock = MagicMock()
    legacy_mock = MagicMock(return_value=legacy_result)
    monkeypatch.setattr(
        "app.services.agent.query_service.settings.knowledge_retrieval_mode",
        "legacy",
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.retrieve_with_llamaindex",
        llamaindex_mock,
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.retrieve_relevant_chunks",
        legacy_mock,
    )
    monkeypatch.setattr(
        "app.services.agent.query_service.generate_rag_answer",
        MagicMock(return_value={
            "answer": "test", "answer_source": "llm", "model": "mock",
            "answered_at": "2024-01-01", "answer_latency_ms": 1.0,
            "chat_provider": "mock", "chat_model": "mock",
        }),
    )

    result = run_query_with_context(
        "doc.txt",
        "test question",
        top_k=3,
        execution_context="eval",
    )
    assert result.filename == "doc.txt"
    llamaindex_mock.assert_not_called()
    legacy_mock.assert_called_once()
