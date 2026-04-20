from pathlib import Path
import json
import shutil
import uuid

from app.services.ingestion.external_ticket_import_service import (
    import_normalized_tickets_to_store,
)


TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TMP_ROOT.mkdir(exist_ok=True)


def _make_tmp_dir() -> Path:
    path = TMP_ROOT / f"external_ticket_import_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_import_normalized_tickets_to_store_merges_without_overwriting(monkeypatch):
    import app.services.agent.tool_service as tool_service_module
    import app.services.ingestion.external_ticket_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        ticket_store_path = tmp_dir / "tickets.json"
        bundle_path = tmp_dir / "bundle.normalized.json"

        ticket_store_path.write_text(
            json.dumps(
                [
                    {
                        "ticket_id": "BUGSREPO_STRUCTURED-101",
                        "target": "payment-service",
                        "service": "payment-service",
                        "status": "open",
                        "severity": "high",
                        "environment": "production",
                        "created_at": "2026-04-10T00:00:00+00:00",
                        "updated_at": "2026-04-10T00:00:00+00:00",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "bugsrepo_structured"},
                    "tickets": [
                        {
                            "ticket_id": "BUGSREPO_STRUCTURED-101",
                            "title": "Existing ticket should be skipped",
                            "service": "payment-service",
                            "environment": "production",
                            "severity": "low",
                            "status": "closed",
                            "created_at": "2026-04-09T00:00:00+00:00",
                            "updated_at": "2026-04-09T00:00:00+00:00",
                            "summary": "skip me",
                        },
                        {
                            "ticket_id": "BUGSREPO_STRUCTURED-102",
                            "title": "New imported ticket",
                            "service": "core-layout",
                            "environment": "unspecified",
                            "severity": "medium",
                            "status": "closed",
                            "created_at": "2026-04-11T00:00:00+00:00",
                            "updated_at": "2026-04-11T00:00:00+00:00",
                            "summary": "import me",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(tool_service_module, "TICKET_STORE_PATH", ticket_store_path)
        monkeypatch.setattr(import_module.tool_service, "TICKET_STORE_PATH", ticket_store_path)

        result = import_normalized_tickets_to_store(bundle_path)

        stored = json.loads(ticket_store_path.read_text(encoding="utf-8"))
        assert result["imported_count"] == 1
        assert result["skipped_count"] == 1
        assert len(stored) == 2
        assert any(ticket["ticket_id"] == "BUGSREPO_STRUCTURED-102" for ticket in stored)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_import_normalized_tickets_to_store_can_overwrite_existing(monkeypatch):
    import app.services.agent.tool_service as tool_service_module
    import app.services.ingestion.external_ticket_import_service as import_module

    tmp_dir = _make_tmp_dir()
    try:
        ticket_store_path = tmp_dir / "tickets.json"
        bundle_path = tmp_dir / "bundle.normalized.json"

        ticket_store_path.write_text(
            json.dumps(
                [
                    {
                        "ticket_id": "IT_SUPPORT_V2-1",
                        "target": "it-support",
                        "service": "it-support",
                        "status": "open",
                        "severity": "unspecified",
                        "environment": "unspecified",
                        "created_at": "2026-04-10T00:00:00+00:00",
                        "updated_at": "2026-04-10T00:00:00+00:00",
                        "summary": "old summary",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        bundle_path.write_text(
            json.dumps(
                {
                    "dataset": {"slug": "it_support_v2"},
                    "tickets": [
                        {
                            "ticket_id": "IT_SUPPORT_V2-1",
                            "title": "Updated support dialogue",
                            "service": "it-support",
                            "environment": "unspecified",
                            "severity": "unspecified",
                            "status": "open",
                            "created_at": "2026-04-10T00:00:00+00:00",
                            "updated_at": "2026-04-12T00:00:00+00:00",
                            "summary": "new summary",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(tool_service_module, "TICKET_STORE_PATH", ticket_store_path)
        monkeypatch.setattr(import_module.tool_service, "TICKET_STORE_PATH", ticket_store_path)

        result = import_normalized_tickets_to_store(bundle_path, overwrite_existing=True)

        stored = json.loads(ticket_store_path.read_text(encoding="utf-8"))
        assert result["updated_count"] == 1
        assert stored[0]["summary"] == "new summary"
        assert stored[0]["import_source"] == "it_support_v2"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
