from app.services.vectorstore import qdrant_index_service


def test_list_persisted_embedding_filenames_prefers_raw_suffixes(workspace_tmp_path, monkeypatch):
    embedding_dir = workspace_tmp_path / "embeddings"
    raw_dir = workspace_tmp_path / "raw"
    embedding_dir.mkdir()
    raw_dir.mkdir()
    (embedding_dir / "rag_overview.embeddings.json").write_text("{}", encoding="utf-8")
    (embedding_dir / "notes.embeddings.json").write_text("{}", encoding="utf-8")
    (raw_dir / "rag_overview.md").write_text("# hi", encoding="utf-8")
    (raw_dir / "notes.txt").write_text("hello", encoding="utf-8")

    monkeypatch.setattr(qdrant_index_service, "EMBEDDING_DATA_DIR", embedding_dir)

    filenames = qdrant_index_service.list_persisted_embedding_filenames()

    assert filenames == ["notes.txt", "rag_overview.md"]


def test_sync_all_persisted_embeddings_to_qdrant_collects_results(monkeypatch):
    monkeypatch.setattr(
        qdrant_index_service,
        "list_persisted_embedding_filenames",
        lambda: ["a.md", "b.md"],
    )

    def fake_sync(filename):
        if filename == "a.md":
            return {
                "synced": True,
                "point_count": 3,
                "collection_name": "agent_knowledge_chunks",
            }
        raise RuntimeError("boom")

    monkeypatch.setattr(qdrant_index_service, "sync_document_embeddings_to_qdrant", fake_sync)

    summary = qdrant_index_service.sync_all_persisted_embeddings_to_qdrant()

    assert summary["document_count"] == 2
    assert summary["synced_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["results"][0]["filename"] == "a.md"
    assert summary["results"][1]["warning"] == "boom"
