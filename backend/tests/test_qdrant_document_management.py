from types import SimpleNamespace

from app.core.config import settings
from app.storage.vector import qdrant_client


def test_has_qdrant_points_for_document_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(settings, "qdrant_local_path", "")

    assert qdrant_client.has_qdrant_points_for_document("sample.txt") is False


def test_has_qdrant_points_for_document_uses_count_filter(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")
    operations = {}

    class DummyClient:
        def count(self, **kwargs):
            operations["count"] = kwargs
            return SimpleNamespace(count=2)

    rest = SimpleNamespace(
        Filter=lambda **kwargs: SimpleNamespace(**kwargs),
        FieldCondition=lambda **kwargs: SimpleNamespace(**kwargs),
        MatchValue=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    monkeypatch.setattr(qdrant_client, "build_qdrant_client", lambda: DummyClient())
    monkeypatch.setattr(qdrant_client, "_import_qdrant_client", lambda: (object, rest))

    assert qdrant_client.has_qdrant_points_for_document("sample.txt") is True
    assert operations["count"]["exact"] is True


def test_delete_qdrant_points_for_document_deletes_by_filename(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")
    operations = {}

    class DummyClient:
        def delete(self, **kwargs):
            operations["delete"] = kwargs

    rest = SimpleNamespace(
        FilterSelector=lambda **kwargs: SimpleNamespace(**kwargs),
        Filter=lambda **kwargs: SimpleNamespace(**kwargs),
        FieldCondition=lambda **kwargs: SimpleNamespace(**kwargs),
        MatchValue=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    monkeypatch.setattr(qdrant_client, "build_qdrant_client", lambda: DummyClient())
    monkeypatch.setattr(qdrant_client, "_import_qdrant_client", lambda: (object, rest))

    result = qdrant_client.delete_qdrant_points_for_document("sample.txt")

    assert result["deleted"] is True
    assert operations["delete"]["wait"] is True


def test_has_qdrant_points_for_document_returns_false_when_client_missing(monkeypatch):
    monkeypatch.setattr(settings, "qdrant_local_path", "tmp/qdrant")
    monkeypatch.setattr(settings, "qdrant_url", "")
    monkeypatch.setattr(
        qdrant_client,
        "_import_qdrant_client",
        lambda: (_ for _ in ()).throw(RuntimeError("qdrant_client_not_installed")),
    )

    assert qdrant_client.has_qdrant_points_for_document("sample.txt") is False
