from pathlib import Path
import json
import shutil
import uuid

from app.services.ingestion.external_knowledge_import_service import (
    import_normalized_knowledge_assets,
    persist_imported_knowledge_assets,
)


TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TMP_ROOT.mkdir(exist_ok=True)


def _make_tmp_dir() -> Path:
    path = TMP_ROOT / f"external_knowledge_import_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_import_normalized_knowledge_assets_writes_markdown(monkeypatch):
    import app.services.ingestion.external_knowledge_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        raw_dir = tmp_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = tmp_dir / "bundle.normalized.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "customer_support_tickets"},
                    "knowledge_assets": [
                        {
                            "doc_id": "customer_support_tickets::1",
                            "service": "technical-support",
                            "doc_kind": "support_ticket",
                            "tags": ["incident", "technical support"],
                            "source_filename": "customer_support_tickets_1.md",
                            "title": "Account Disruption",
                            "snippet": "The centralized account management portal appears offline.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(import_module, "get_document_path", lambda filename: raw_dir / filename)

        result = import_normalized_knowledge_assets(bundle_path)

        created = raw_dir / "customer_support_tickets_1.md"
        assert result["imported_count"] == 1
        assert result["skipped_count"] == 0
        assert created.exists()
        content = created.read_text(encoding="utf-8")
        assert "# Account Disruption" in content
        assert "technical-support" in content
        assert "The centralized account management portal appears offline." in content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_import_normalized_knowledge_assets_skips_existing_by_default(monkeypatch):
    import app.services.ingestion.external_knowledge_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        raw_dir = tmp_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        existing = raw_dir / "it_support_v2_1.md"
        existing.write_text("existing content", encoding="utf-8")

        bundle_path = tmp_dir / "bundle.normalized.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "it_support_v2"},
                    "knowledge_assets": [
                        {
                            "doc_id": "it_support_v2::1",
                            "service": "it-support",
                            "doc_kind": "support_resolution",
                            "tags": ["support-dialogue"],
                            "source_filename": "it_support_v2_1.md",
                            "title": "Outlook cannot read emails",
                            "snippet": "Check mailbox quotas and Outlook cache settings.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(import_module, "get_document_path", lambda filename: raw_dir / filename)

        result = import_normalized_knowledge_assets(bundle_path)

        assert result["imported_count"] == 0
        assert result["skipped_count"] == 1
        assert existing.read_text(encoding="utf-8") == "existing content"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_persist_imported_knowledge_assets_builds_chunks_embeddings_and_qdrant(monkeypatch):
    import app.services.ingestion.external_knowledge_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        raw_dir = tmp_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        document = raw_dir / "customer_support_tickets_2.md"
        document.write_text("# Imported", encoding="utf-8")

        bundle_path = tmp_dir / "bundle.normalized.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "customer_support_tickets"},
                    "knowledge_assets": [
                        {"source_filename": "customer_support_tickets_2.md"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        chunk_calls: list[str] = []
        embedding_calls: list[str] = []
        qdrant_calls: list[str] = []

        monkeypatch.setattr(import_module, "get_document_path", lambda filename: raw_dir / filename)
        monkeypatch.setattr(import_module, "persist_document_chunks", lambda filename: chunk_calls.append(filename))
        monkeypatch.setattr(import_module, "persist_document_embeddings", lambda filename: embedding_calls.append(filename))
        monkeypatch.setattr(
            import_module,
            "sync_document_embeddings_to_qdrant",
            lambda filename: qdrant_calls.append(filename) or {"synced": True},
        )
        monkeypatch.setattr(
            import_module,
            "get_document_asset_status",
            lambda filename: {
                "filename": filename,
                "knowledge_assets": {
                    "chunks_ready": True,
                    "embeddings_ready": True,
                    "llamaindex_ready": False,
                    "qdrant_ready": True,
                },
            },
        )

        result = persist_imported_knowledge_assets(bundle_path)

        assert result["chunked_count"] == 1
        assert result["embedded_count"] == 1
        assert result["qdrant_synced_count"] == 1
        assert chunk_calls == ["customer_support_tickets_2.md"]
        assert embedding_calls == ["customer_support_tickets_2.md"]
        assert qdrant_calls == ["customer_support_tickets_2.md"]
        assert result["results"][0]["knowledge_assets"]["qdrant_ready"] is True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_persist_imported_knowledge_assets_skips_missing_raw_documents(monkeypatch):
    import app.services.ingestion.external_knowledge_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        raw_dir = tmp_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = tmp_dir / "bundle.normalized.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "it_support_v2"},
                    "knowledge_assets": [
                        {"source_filename": "missing_doc.md"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(import_module, "get_document_path", lambda filename: raw_dir / filename)

        result = persist_imported_knowledge_assets(bundle_path)

        assert result["chunked_count"] == 0
        assert result["embedded_count"] == 0
        assert result["qdrant_synced_count"] == 0
        assert result["skipped_count"] == 1
        assert result["results"][0]["warning"] == "raw_document_missing"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_persist_imported_knowledge_assets_keeps_processing_when_qdrant_sync_fails(monkeypatch):
    import app.services.ingestion.external_knowledge_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        raw_dir = tmp_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        document = raw_dir / "it_support_v2_2.md"
        document.write_text("# Imported", encoding="utf-8")

        bundle_path = tmp_dir / "bundle.normalized.json"
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "it_support_v2"},
                    "knowledge_assets": [
                        {"source_filename": "it_support_v2_2.md"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(import_module, "get_document_path", lambda filename: raw_dir / filename)
        monkeypatch.setattr(import_module, "persist_document_chunks", lambda filename: None)
        monkeypatch.setattr(import_module, "persist_document_embeddings", lambda filename: None)
        monkeypatch.setattr(
            import_module,
            "sync_document_embeddings_to_qdrant",
            lambda filename: (_ for _ in ()).throw(RuntimeError("qdrant_locked")),
        )
        monkeypatch.setattr(
            import_module,
            "get_document_asset_status",
            lambda filename: {
                "filename": filename,
                "knowledge_assets": {
                    "chunks_ready": True,
                    "embeddings_ready": True,
                    "llamaindex_ready": False,
                    "qdrant_ready": False,
                },
            },
        )

        result = persist_imported_knowledge_assets(bundle_path)

        assert result["chunked_count"] == 1
        assert result["embedded_count"] == 1
        assert result["qdrant_synced_count"] == 0
        assert result["results"][0]["warning"] == "qdrant_locked"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
