from app.storage.cache.redis_client import _normalize_redis_url


def test_normalize_redis_url_rewrites_localhost_to_loopback():
    assert _normalize_redis_url("redis://localhost:6379/0") == "redis://127.0.0.1:6379/0"


def test_normalize_redis_url_preserves_remote_hosts():
    assert _normalize_redis_url("redis://cache.internal:6379/0") == "redis://cache.internal:6379/0"
