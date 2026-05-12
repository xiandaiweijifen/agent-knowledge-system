from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.retrieval import qdrant_retrieval_service


def test_retrieve_with_qdrant_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "")

    with pytest.raises(FileNotFoundError):
        qdrant_retrieval_service.retrieve_with_qdrant("sample.txt", "what is rag?")


def test_retrieve_with_qdrant_returns_retrieval_result(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(
        qdrant_retrieval_service,
        "_load_embedding_metadata",
        lambda filename: SimpleNamespace(
            filename=filename,
            embedding_provider="mock",
            embedding_model="mock-embedding-v1",
            vector_dim=8,
        ),
    )
    monkeypatch.setattr(
        qdrant_retrieval_service,
        "generate_query_embedding",
        lambda *args, **kwargs: ("mock", "mock-embedding-v1", [0.1] * 8),
    )
    monkeypatch.setattr(
        qdrant_retrieval_service,
        "_query_qdrant_points",
        lambda query_vector, source_filename, limit: [
            {
                "chunk_id": "sample.txt::chunk_0",
                "content": "RAG combines retrieval with generation.",
                "score": 0.81,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "sample.txt",
                    "source_suffix": ".txt",
                    "document_kind": "overview",
                    "char_count": 40,
                    "section_title": "Overview",
                    "section_path": ["Overview"],
                    "heading_level": 1,
                },
            }
        ],
    )

    result = qdrant_retrieval_service.retrieve_with_qdrant(
        "sample.txt",
        "What is RAG?",
        top_k=1,
    )

    assert result.embedding_provider == "qdrant"
    assert result.filename == "sample.txt"
    assert result.matches[0].chunk_id == "sample.txt::chunk_0"


def test_retrieve_with_qdrant_corpus_merges_multiple_documents(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(
        qdrant_retrieval_service,
        "_list_qdrant_candidate_documents",
        lambda: ["doc_a.md", "doc_b.md"],
    )
    monkeypatch.setattr(
        qdrant_retrieval_service,
        "_load_embedding_metadata",
        lambda filename: SimpleNamespace(
            filename=filename,
            embedding_provider="mock",
            embedding_model="mock-embedding-v1",
            vector_dim=8,
        ),
    )
    monkeypatch.setattr(
        qdrant_retrieval_service,
        "generate_query_embedding",
        lambda *args, **kwargs: ("mock", "mock-embedding-v1", [0.1] * 8),
    )

    calls = []

    def fake_query(query_vector, source_filenames, limit):
        calls.append({"source_filenames": source_filenames, "limit": limit})
        return [
            {
                "chunk_id": "doc_a.md::chunk_0",
                "content": "RAG improves factual grounding.",
                "score": 0.73,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "doc_a.md",
                    "source_suffix": ".md",
                    "document_kind": "overview",
                    "char_count": 32,
                    "section_title": "Overview",
                    "section_path": ["Overview"],
                    "heading_level": 1,
                },
            },
            {
                "chunk_id": "doc_b.md::chunk_0",
                "content": "Weak embeddings are a common failure mode.",
                "score": 0.79,
                "metadata": {
                    "chunk_index": 0,
                    "source_filename": "doc_b.md",
                    "source_suffix": ".md",
                    "document_kind": "overview",
                    "char_count": 42,
                    "section_title": "Failure Modes",
                    "section_path": ["RAG", "Failure Modes"],
                    "heading_level": 2,
                }
            },
        ]

    monkeypatch.setattr(qdrant_retrieval_service, "_query_qdrant_points_for_filenames", fake_query)

    result = qdrant_retrieval_service.retrieve_with_qdrant_corpus(
        "Explain common failure modes",
        top_k=2,
    )

    assert result.retrieval_scope == "corpus"
    assert result.corpus_filenames == ["doc_a.md", "doc_b.md"]
    assert len(result.matches) == 2
    assert result.matches[0].source_filename == "doc_b.md"
    assert calls == [{"source_filenames": ["doc_a.md", "doc_b.md"], "limit": 4}]
