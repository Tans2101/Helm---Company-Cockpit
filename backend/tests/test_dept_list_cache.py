"""Department list cache invalidates on write (freshness for CEO views)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_dept_list_cache")

import simple_cache  # noqa: E402
import server  # noqa: E402


def setup_function():
    simple_cache.clear()


def test_list_cache_put_peek_and_invalidate_on_write_kind():
    key = server._list_cache_key("production", "ws1", "u1", "dept1", "all")
    simple_cache.put(key, {"work_orders": [{"id": "old"}]}, 30.0)
    assert simple_cache.peek(key)["work_orders"][0]["id"] == "old"
    server.invalidate_workspace_list_cache("ws1", "production")
    assert simple_cache.peek(key) is None


def test_financials_invalidate_also_clears_page_cache():
    page_key = server._list_cache_key("financials_page", "ws1", "all")
    simple_cache.put(page_key, {"entries": []}, 30.0)
    simple_cache.put("financials:ws1", {"fin": {}}, 30.0)
    server.invalidate_financials_cache("ws1")
    assert simple_cache.peek(page_key) is None
    assert simple_cache.peek("financials:ws1") is None


def test_deals_and_hr_kinds_invalidate():
    deals = server._list_cache_key("deals", "ws1", "u1", "all", "", "50")
    hr = server._list_cache_key("hr", "ws1", "u1", "employees", "all")
    people = server._list_cache_key("people", "ws1", "u1")
    simple_cache.put(deals, {"items": []}, 30.0)
    simple_cache.put(hr, {"employees": []}, 30.0)
    simple_cache.put(people, {"people": []}, 30.0)
    server.invalidate_workspace_list_cache("ws1", "deals", "hr")
    assert simple_cache.peek(deals) is None
    assert simple_cache.peek(hr) is None
    assert simple_cache.peek(people) is not None  # people not in invalidate list
