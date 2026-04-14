from app.services.vectorstore import index_service


def test_build_vector_index_delegates_to_llamaindex(monkeypatch):
    monkeypatch.setattr(
        index_service,
        "build_llamaindex_index",
        lambda filename: {"filename": filename, "node_count": 2, "store_path": "demo"},
    )

    result = index_service.build_vector_index("demo.txt")

    assert result["filename"] == "demo.txt"
    assert result["node_count"] == 2


def test_has_vector_index_delegates_to_llamaindex(monkeypatch):
    monkeypatch.setattr(index_service, "has_llamaindex_index", lambda filename: filename == "demo.txt")

    assert index_service.has_vector_index("demo.txt") is True
    assert index_service.has_vector_index("other.txt") is False

