import json

from app.services.ingestion import document_service


def test_persist_document_chunks_stores_chunk_strategy(
    workspace_tmp_path,
    monkeypatch,
):
    raw_dir = workspace_tmp_path / "raw"
    chunk_dir = workspace_tmp_path / "chunks"
    raw_dir.mkdir()
    chunk_dir.mkdir()

    monkeypatch.setattr(document_service, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(document_service, "CHUNK_DATA_DIR", chunk_dir)

    (raw_dir / "sample.md").write_text(
        "# Title\n\nParagraph one.\n\nParagraph two.\n\nParagraph three.",
        encoding="utf-8",
    )

    result = document_service.persist_document_chunks(
        filename="sample.md",
        chunk_size=40,
        chunk_overlap=10,
        chunk_strategy="paragraph",
    )
    persisted_payload = json.loads(
        (chunk_dir / "sample.chunks.json").read_text(encoding="utf-8")
    )

    assert result["chunk_strategy"] == "paragraph"
    assert persisted_payload["chunk_strategy"] == "paragraph"
    assert persisted_payload["chunk_count"] >= 2
