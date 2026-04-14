from types import SimpleNamespace
import uuid

from app.core.config import settings
from app.storage.vector import qdrant_client


def test_qdrant_enabled_uses_url_or_local_path(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "")
    assert qdrant_client.qdrant_enabled() is False

    monkeypatch.setattr(settings, "qdrant_url", "http://localhost:6333")
    assert qdrant_client.qdrant_enabled() is True


def test_get_qdrant_collection_name_normalizes_invalid_chars(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_collection_name", " Agent Knowledge/Chunks ")

    assert qdrant_client.get_qdrant_collection_name() == "agent_knowledge_chunks"


def test_build_qdrant_client_returns_none_when_unconfigured(monkeypatch):
    qdrant_client.reset_qdrant_client_cache()
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "")

    assert qdrant_client.build_qdrant_client() is None


def test_build_qdrant_client_uses_local_path(monkeypatch):
    qdrant_client.reset_qdrant_client_cache()
    captured = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(
        qdrant_client,
        "_import_qdrant_client",
        lambda: (DummyClient, SimpleNamespace()),
    )

    client = qdrant_client.build_qdrant_client()

    assert isinstance(client, DummyClient)
    assert captured == {"path": "tmp/qdrant"}


def test_build_qdrant_client_uses_remote_url(monkeypatch):
    qdrant_client.reset_qdrant_client_cache()
    captured = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(settings, "qdrant_url", "http://localhost:6333")
    monkeypatch.setattr(settings, "qdrant_local_path", "")
    monkeypatch.setattr(settings, "qdrant_api_key", "secret")
    monkeypatch.setattr(settings, "qdrant_prefer_grpc", True)
    monkeypatch.setattr(
        qdrant_client,
        "_import_qdrant_client",
        lambda: (DummyClient, SimpleNamespace()),
    )

    client = qdrant_client.build_qdrant_client()

    assert isinstance(client, DummyClient)
    assert captured == {
        "url": "http://localhost:6333",
        "api_key": "secret",
        "prefer_grpc": True,
    }


def test_build_qdrant_client_reuses_cached_instance(monkeypatch):
    qdrant_client.reset_qdrant_client_cache()
    created = {"count": 0}

    class DummyClient:
        def __init__(self, **kwargs):
            created["count"] += 1

    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(
        qdrant_client,
        "_import_qdrant_client",
        lambda: (DummyClient, SimpleNamespace()),
    )

    first = qdrant_client.build_qdrant_client()
    second = qdrant_client.build_qdrant_client()

    assert first is second
    assert created["count"] == 1


def test_build_qdrant_payload_maps_embedding_record_fields():
    record = SimpleNamespace(
        chunk_id="doc.md::chunk_0",
        chunk_index=0,
        source_filename="doc.md",
        source_suffix=".md",
        document_kind="overview",
        char_count=128,
        section_title="Intro",
        section_path=["Doc", "Intro"],
        heading_level=2,
        content="hello world",
    )

    payload = qdrant_client.build_qdrant_payload(
        filename="doc.md",
        embedding_record=record,
    )

    assert payload["chunk_id"] == "doc.md::chunk_0"
    assert payload["source_filename"] == "doc.md"
    assert payload["corpus_document_id"] == "doc.md"
    assert payload["section_path"] == ["Doc", "Intro"]


def test_build_qdrant_point_id_returns_stable_uuid():
    point_id = qdrant_client.build_qdrant_point_id("doc.md::chunk_0")

    assert point_id == qdrant_client.build_qdrant_point_id("doc.md::chunk_0")
    assert str(uuid.UUID(point_id)) == point_id


def test_close_qdrant_clients_closes_cached_instances(monkeypatch):
    qdrant_client.reset_qdrant_client_cache()
    closed = {"count": 0}

    class DummyClient:
        def close(self):
            closed["count"] += 1

    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(
        qdrant_client,
        "_import_qdrant_client",
        lambda: (lambda **kwargs: DummyClient(), SimpleNamespace()),
    )

    qdrant_client.build_qdrant_client()
    qdrant_client.close_qdrant_clients()

    assert closed["count"] == 1
