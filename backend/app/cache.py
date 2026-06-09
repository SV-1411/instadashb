"""Tiny Redis JSON cache for dashboard read paths (architecture rule 1).

If Redis is unavailable the cache transparently degrades to a miss — the API
still serves fresh data from Postgres rather than erroring.
"""

from __future__ import annotations

import json
from typing import Any, cast

import redis

from app.config import get_settings
from app.core.logging import get_logger

log = get_logger("cache")

_client: redis.Redis | None = None


def _redis() -> redis.Redis | None:
    global _client
    if _client is None:
        try:
            _client = redis.Redis.from_url(
                get_settings().redis_url, socket_connect_timeout=2, decode_responses=True
            )
        except Exception:  # noqa: BLE001
            return None
    return _client


def cache_get(key: str) -> Any | None:
    try:
        client = _redis()
        if client is None:
            return None
        raw = cast("str | None", client.get(key))
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001 - cache must never break a read
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        client = _redis()
        if client is None:
            return
        ttl = ttl if ttl is not None else get_settings().dashboard_cache_ttl_seconds
        client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:  # noqa: BLE001
        log.warning("cache_set_failed", key=key)
