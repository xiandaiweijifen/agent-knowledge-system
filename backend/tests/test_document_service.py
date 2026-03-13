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
