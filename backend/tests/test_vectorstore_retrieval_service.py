from types import SimpleNamespace

from app.services.vectorstore import retrieval_service


def test_retrieve_with_vector_index_delegates_to_llamaindex(monkeypatch):
    expected = SimpleNamespace(filename="demo.txt", top_k=2)
    monkeypatch.setattr(
        retrieval_service,
        "retrieve_with_llamaindex",
        lambda filename, query_text, top_k=3: expected,
    )

    result = retrieval_service.retrieve_with_vector_index(
        filename="demo.txt",
        query_text="agent runtime",
        top_k=2,
    )

    assert result is expected


def test_retrieve_with_vector_index_corpus_delegates_to_llamaindex(monkeypatch):
    expected = SimpleNamespace(retrieval_scope="corpus", top_k=4)
    monkeypatch.setattr(
        retrieval_service,
        "retrieve_with_llamaindex_corpus",
        lambda query_text, top_k=3, filenames=None: expected,
    )

    result = retrieval_service.retrieve_with_vector_index_corpus(
        query_text="agent runtime",
        top_k=4,
        filenames=["a.md", "b.md"],
    )

    assert result is expected
