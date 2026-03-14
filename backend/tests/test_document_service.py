from pathlib import Path

import pytest

from app.services.ingestion import document_service


def test_list_documents_filters_hidden_and_non_document_files(
    workspace_tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", workspace_tmp_path)

    (workspace_tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (workspace_tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (workspace_tmp_path / "design.md").write_text("# title", encoding="utf-8")
    (workspace_tmp_path / "image.png").write_bytes(b"binary")

    documents = document_service.list_documents()

    assert documents == [
        {
            "filename": "design.md",
            "size_bytes": len("# title".encode("utf-8")),
            "suffix": ".md",
        },
        {
            "filename": "notes.txt",
            "size_bytes": len("hello".encode("utf-8")),
            "suffix": ".txt",
        },
    ]


def test_read_text_document_raises_decode_error_for_non_utf8_file(
    workspace_tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(document_service, "RAW_DATA_DIR", workspace_tmp_path)

    invalid_utf8_path = workspace_tmp_path / "latin1.txt"
    invalid_utf8_path.write_bytes("caf\xe9".encode("latin-1"))

    with pytest.raises(ValueError, match="text_decode_error"):
        document_service.read_text_document("latin1.txt")


def test_delete_document_with_artifacts_removes_related_files(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    chunk_dir = workspace_tmp_path / "chunks"
    embedding_dir = workspace_tmp_path / "embeddings"
    raw_dir.mkdir()
    chunk_dir.mkdir()
    embedding_dir.mkdir()

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(document_service, "CHUNK_DATA_DIR", chunk_dir)

    target_name = "notes.md"
    (raw_dir / target_name).write_text("# notes", encoding="utf-8")
    (chunk_dir / "notes.chunks.json").write_text("{}", encoding="utf-8")

    from app.services.indexing import embedding_service

    monkeypatch.setattr(embedding_service, "EMBEDDING_DATA_DIR", embedding_dir)
    (embedding_dir / "notes.embeddings.json").write_text("{}", encoding="utf-8")

    removed_paths = []

    def fake_unlink(self):
        removed_paths.append(str(self))

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    payload = document_service.delete_document_with_artifacts(target_name)

    assert payload == {
        "filename": target_name,
        "deleted_document": True,
        "deleted_chunks": True,
        "deleted_embeddings": True,
    }
    assert str(raw_dir / target_name) in removed_paths
    assert str(chunk_dir / "notes.chunks.json") in removed_paths
    assert str(embedding_dir / "notes.embeddings.json") in removed_paths
