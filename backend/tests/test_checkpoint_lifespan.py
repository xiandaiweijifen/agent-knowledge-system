from app.storage.db import checkpoint


def test_normalize_url_rewrites_localhost_to_loopback():
    assert (
        checkpoint._normalize_url(
            "postgresql://postgres:password@localhost:5432/agent_knowledge_system"
        )
        == "postgresql://postgres:password@127.0.0.1:5432/agent_knowledge_system"
    )


def test_normalize_url_preserves_sqlalchemy_driver_cleanup():
    assert (
        checkpoint._normalize_url(
            "postgresql+psycopg2://postgres:password@localhost:5432/agent_knowledge_system"
        )
        == "postgresql://postgres:password@127.0.0.1:5432/agent_knowledge_system"
    )


class FakeConnection:
    def __init__(self, name: str):
        self.name = name
        self.closed = False
        self.setup_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed = True


def test_windows_sync_checkpointer_uses_single_closeable_connection(monkeypatch):
    connections: list[FakeConnection] = []
    saver_connections: list[FakeConnection] = []

    def fake_connect(*args, **kwargs):
        connection = FakeConnection(f"conn-{len(connections) + 1}")
        connections.append(connection)
        return connection

    class FakePostgresSaver:
        def __init__(self, conn):
            saver_connections.append(conn)
            self.conn = conn

        def setup(self):
            self.conn.setup_called = True

    monkeypatch.setattr(checkpoint.psycopg.Connection, "connect", fake_connect)
    monkeypatch.setattr(checkpoint, "PostgresSaver", FakePostgresSaver)

    checkpointer, closeable = checkpoint._build_sync_checkpointer("postgresql://example")

    assert checkpointer is not None
    assert closeable is connections[1]
    assert connections[0].setup_called is True
    assert connections[0].closed is True
    assert connections[1].closed is False
    closeable.close()
    assert connections[1].closed is True
    assert saver_connections == connections
