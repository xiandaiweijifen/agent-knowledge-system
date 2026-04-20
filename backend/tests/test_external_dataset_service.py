from pathlib import Path
import shutil
import uuid

from app.services.ingestion.external_dataset_service import (
    list_external_dataset_targets,
    load_external_dataset_records,
    normalize_ticket_dataset_records,
    write_normalized_external_dataset,
)


TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TMP_ROOT.mkdir(exist_ok=True)


def _make_tmp_dir() -> Path:
    path = TMP_ROOT / f"external_dataset_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_list_external_dataset_targets_includes_bugsrepo():
    targets = list_external_dataset_targets()
    assert any(target["slug"] == "bugsrepo_structured" for target in targets)
    assert any(target["slug"] == "customer_support_tickets" for target in targets)
    assert any(target["slug"] == "it_support_v2" for target in targets)


def test_normalize_ticket_dataset_records_maps_to_domain_bundle():
    records = [
        {
            "bug_id": "101",
            "summary": "Payment service timeout spikes in production",
            "description": "Observed repeated timeout spikes after a downstream database latency increase.",
            "status": "RESOLVED",
            "severity": "critical",
            "product": "payment-service",
            "environment": "production",
            "assigned_to": "oncall@example.com",
            "created_at": "2026-04-10T00:00:00+00:00",
            "updated_at": "2026-04-10T01:00:00+00:00",
            "comments": [
                {"body": "Primary mitigation was to reduce retry pressure."},
            ],
        }
    ]

    bundle = normalize_ticket_dataset_records("bugsrepo_structured", records)

    assert bundle["ticket_count"] == 1
    assert bundle["service_count"] == 1
    assert bundle["knowledge_asset_count"] == 1
    assert bundle["tickets"][0]["ticket_id"] == "BUGSREPO_STRUCTURED-101"
    assert bundle["tickets"][0]["severity"] == "high"
    assert bundle["tickets"][0]["status"] == "closed"
    assert bundle["tickets"][0]["service"] == "payment-service"
    assert bundle["services"][0]["service_id"] == "payment-service"
    assert bundle["knowledge_assets"][0]["doc_kind"] == "issue_report"


def test_normalize_customer_support_tickets_maps_queue_and_tags():
    records = [
        {
            "subject": "Account Disruption",
            "body": "The centralized account management portal appears offline.",
            "answer": "We are aware of the outage and are investigating.",
            "type": "Incident",
            "queue": "Technical Support",
            "priority": "high",
            "language": "en",
            "tag_1": "Account",
            "tag_2": "Outage",
            "tag_3": "",
        }
    ]

    bundle = normalize_ticket_dataset_records("customer_support_tickets", records)

    assert bundle["ticket_count"] == 1
    assert bundle["tickets"][0]["severity"] == "high"
    assert bundle["tickets"][0]["service"] == "technical-support"
    assert bundle["knowledge_assets"][0]["doc_kind"] == "support_ticket"
    assert "technical support" in bundle["knowledge_assets"][0]["tags"]
    assert "incident" in bundle["knowledge_assets"][0]["tags"]


def test_normalize_it_support_v2_uses_dialogue_messages():
    records = [
        {
            "messages": [
                {"role": "user", "content": "Outlook cannot read emails from Exchange with large attachments."},
                {"role": "assistant", "content": "Check mailbox quotas and Outlook cache settings."},
            ]
        }
    ]

    bundle = normalize_ticket_dataset_records("it_support_v2", records)

    assert bundle["ticket_count"] == 1
    assert bundle["services"][0]["service_id"] == "it-support"
    assert bundle["tickets"][0]["summary"].startswith("Outlook cannot read emails")
    assert bundle["knowledge_assets"][0]["doc_kind"] == "support_resolution"
    assert "Check mailbox quotas" in bundle["knowledge_assets"][0]["snippet"]


def test_load_external_dataset_records_supports_jsonl():
    tmp_dir = _make_tmp_dir()
    try:
        input_path = tmp_dir / "sample.jsonl"
        input_path.write_text('{"bug_id":"1","summary":"One"}\n{"bug_id":"2","summary":"Two"}\n', encoding="utf-8")

        records = load_external_dataset_records(input_path)

        assert len(records) == 2
        assert records[0]["bug_id"] == "1"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_write_normalized_external_dataset_persists_processed_bundle(monkeypatch):
    import app.services.ingestion.external_dataset_service as module

    tmp_path = _make_tmp_dir()
    try:
        monkeypatch.setattr(module, "EXTERNAL_PROCESSED_ROOT", tmp_path)
        bundle = {
            "dataset": {"slug": "bugsrepo_structured"},
            "record_count": 1,
            "ticket_count": 1,
            "service_count": 1,
            "knowledge_asset_count": 1,
            "tickets": [],
            "services": [],
            "knowledge_assets": [],
        }

        output_path = write_normalized_external_dataset("bugsrepo_structured", bundle)

        assert output_path.exists()
        assert output_path.name == "bugsrepo_structured.normalized.json"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
