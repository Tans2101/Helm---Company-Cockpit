"""Unit tests for backend/simple_cache.py."""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_simple_cache")

import simple_cache  # noqa: E402


def setup_function():
    simple_cache.clear()


def test_get_or_set_caches_and_hits():
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        return {"ok": True, "n": calls["n"]}

    async def run():
        a = await simple_cache.get_or_set("k1", 60, loader)
        b = await simple_cache.get_or_set("k1", 60, loader)
        return a, b

    a, b = asyncio.run(run())
    assert a == b == {"ok": True, "n": 1}
    assert calls["n"] == 1
    stats = simple_cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_invalidate_and_prefix():
    async def loader():
        return 1

    asyncio.run(simple_cache.get_or_set("financials:ws_a", 60, loader))
    asyncio.run(simple_cache.get_or_set("financials:ws_a:dept1", 60, loader))
    asyncio.run(simple_cache.get_or_set("financials:ws_b", 60, loader))
    assert simple_cache.invalidate("financials:ws_a") is True
    assert simple_cache.invalidate_prefix("financials:ws_a:") == 1
    assert simple_cache.invalidate_prefix("financials:ws_b") == 1
    assert simple_cache.stats()["entries"] == 0


def test_expired_entry_reloads(monkeypatch):
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        return calls["n"]

    # Force immediate expiry by writing with ttl 0 then advancing monotonic.
    async def run():
        await simple_cache.get_or_set("exp", 0.01, loader)
        # Overwrite expiry into the past
        val, _exp = simple_cache._store["exp"]
        simple_cache._store["exp"] = (val, 0.0)
        return await simple_cache.get_or_set("exp", 60, loader)

    out = asyncio.run(run())
    assert out == 2
    assert calls["n"] == 2
