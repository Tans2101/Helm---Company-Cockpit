"""Minimal in-process TTL cache for single-instance Render deploys.

No Redis / external deps — a plain dict keyed by string with monotonic expiry.
Hit/miss counters make production verification possible via /api/health.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger("helm.cache")

_store: dict[str, tuple[Any, float]] = {}
_hits = 0
_misses = 0


async def get_or_set(
    key: str,
    ttl_seconds: float,
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    """Return cached value if fresh; otherwise await loader(), store, return."""
    global _hits, _misses
    now = time.monotonic()
    row = _store.get(key)
    if row is not None and row[1] > now:
        _hits += 1
        logger.debug("cache hit key=%s", key)
        return row[0]
    _misses += 1
    logger.debug("cache miss key=%s", key)
    value = await loader()
    _store[key] = (value, now + float(ttl_seconds))
    return value


def invalidate(key: str) -> bool:
    """Drop one key. Returns True if it was present."""
    return _store.pop(key, None) is not None


def invalidate_prefix(prefix: str) -> int:
    """Drop every key that starts with prefix. Returns count removed."""
    if not prefix:
        return 0
    dead = [k for k in _store if k.startswith(prefix)]
    for k in dead:
        _store.pop(k, None)
    return len(dead)


def stats() -> dict[str, Any]:
    """Hit/miss/size snapshot for health checks."""
    now = time.monotonic()
    live = sum(1 for _v, exp in _store.values() if exp > now)
    return {
        "hits": _hits,
        "misses": _misses,
        "entries": len(_store),
        "live_entries": live,
        "hit_rate": round(_hits / (_hits + _misses), 4) if (_hits + _misses) else None,
    }


def clear() -> None:
    """Wipe store + counters (tests / process recycle)."""
    global _hits, _misses
    _store.clear()
    _hits = 0
    _misses = 0
