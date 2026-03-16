import json
import time
from threading import Lock
from typing import Any

from app.core.config import settings


_PLANNER_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_PLANNER_CACHE_LOCK = Lock()


def _build_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    serialized_payload = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return f"{namespace}:{serialized_payload}"


def _prune_expired_entries(now: float) -> None:
    expired_keys = [key for key, (expires_at, _) in _PLANNER_CACHE.items() if expires_at <= now]
    for key in expired_keys:
        _PLANNER_CACHE.pop(key, None)


def _prune_oversized_entries() -> None:
    max_entries = max(1, settings.planner_cache_max_entries)
    while len(_PLANNER_CACHE) > max_entries:
        oldest_key = next(iter(_PLANNER_CACHE))
        _PLANNER_CACHE.pop(oldest_key, None)


def get_cached_planner_result(namespace: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    ttl_seconds = settings.planner_cache_ttl_seconds
    if ttl_seconds <= 0:
        return None

    cache_key = _build_cache_key(namespace, payload)
    now = time.monotonic()
    with _PLANNER_CACHE_LOCK:
        _prune_expired_entries(now)
        cached_entry = _PLANNER_CACHE.get(cache_key)
        if cached_entry is None:
            return None
        expires_at, cached_value = cached_entry
        if expires_at <= now:
            _PLANNER_CACHE.pop(cache_key, None)
            return None
        _PLANNER_CACHE.pop(cache_key, None)
        _PLANNER_CACHE[cache_key] = (expires_at, dict(cached_value))
        return dict(cached_value)


def set_cached_planner_result(namespace: str, payload: dict[str, Any], result: dict[str, Any]) -> None:
    ttl_seconds = settings.planner_cache_ttl_seconds
    if ttl_seconds <= 0:
        return

    cache_key = _build_cache_key(namespace, payload)
    expires_at = time.monotonic() + ttl_seconds
    with _PLANNER_CACHE_LOCK:
        _PLANNER_CACHE.pop(cache_key, None)
        _PLANNER_CACHE[cache_key] = (expires_at, dict(result))
        _prune_expired_entries(time.monotonic())
        _prune_oversized_entries()


def clear_planner_cache() -> None:
    with _PLANNER_CACHE_LOCK:
        _PLANNER_CACHE.clear()
