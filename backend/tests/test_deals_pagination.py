"""Cursor pagination for GET /api/deals and GET /api/activities."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_pagination")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402

MOCK_PRINCIPAL = {
    "user_id": "test-user-pagination",
    "email": "paginate@example.com",
    "name": "Paginate Tester",
    "workspace_id": "ws_pagination",
    "role": "owner",
    "pack": "owner",
}


class FakeCursor:
    def __init__(self, items, sort_field: str):
        self._all = list(items)
        self._sort_field = sort_field
        self._filt: dict = {}
        self._limit: int | None = None
        self._projection: dict | None = None

    def sort(self, field, direction):
        assert field == self._sort_field
        self._all.sort(key=lambda x: x[field], reverse=direction == -1)
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def to_list(self, n):
        items = self._all
        ws = self._filt.get("workspace_id")
        if ws is not None:
            items = [i for i in items if i.get("workspace_id") == ws]
        before = self._filt.get(self._sort_field, {})
        if isinstance(before, dict) and "$lt" in before:
            cutoff = before["$lt"]
            items = [i for i in items if i[self._sort_field] < cutoff]
        if self._limit is not None:
            items = items[: self._limit]
        elif n is not None:
            items = items[:n]
        if self._projection:
            exclude_id = self._projection.get("_id") == 0
            include_keys = [k for k, v in self._projection.items() if k != "_id" and v]
            projected = []
            for item in items:
                if include_keys:
                    row = {k: item[k] for k in include_keys if k in item}
                elif exclude_id:
                    row = {k: v for k, v in item.items() if k != "_id"}
                else:
                    row = dict(item)
                projected.append(row)
            return projected
        return items


class FakeAggregateCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, n):
        items = self._rows
        if n is not None:
            items = items[:n]
        return items


class FakeCollection:
    def __init__(self, docs, sort_field: str):
        self._docs = docs
        self._sort_field = sort_field

    def find(self, filt, projection=None):
        cursor = FakeCursor(self._docs, self._sort_field)
        cursor._filt = dict(filt or {})
        cursor._projection = projection
        return cursor

    def aggregate(self, pipeline):
        items = list(self._docs)
        for stage in pipeline:
            if "$match" in stage:
                filt = stage["$match"]
                ws = filt.get("workspace_id")
                if ws is not None:
                    items = [i for i in items if i.get("workspace_id") == ws]
            elif "$group" in stage:
                groups = {}
                for item in items:
                    key = item.get(stage["$group"]["_id"].lstrip("$"))
                    if key not in groups:
                        groups[key] = {"_id": key, "count": 0, "value": 0}
                    groups[key]["count"] += 1
                    groups[key]["value"] += item.get("value", 0)
                items = list(groups.values())
        return FakeAggregateCursor(items)


def _make_deals(n: int, workspace_id: str = "ws_pagination"):
    deals = []
    for i in range(n):
        ts = f"2025-01-01T12:00:{i:02d}Z"
        deals.append(
            {
                "id": f"deal_{i:03d}",
                "workspace_id": workspace_id,
                "name": f"Deal {i}",
                "company": "Co",
                "value": 1000 + i,
                "stage": "lead",
                "owner_name": "Rep",
                "close_date": "",
                "created_at": ts,
                "updated_at": ts,
            }
        )
    return deals


@pytest.fixture
def deals_client():
    async def mock_principal():
        return MOCK_PRINCIPAL

    server.app.dependency_overrides[server.get_principal] = mock_principal
    deals = _make_deals(60)
    mock_db = type("DB", (), {})()
    mock_db.deals = FakeCollection(deals, "updated_at")
    mock_db.activities = FakeCollection([], "created_at")

    with patch.object(server, "db", mock_db):
        yield TestClient(server.app), deals
    server.app.dependency_overrides.clear()


def test_deals_pagination_returns_all_sixty_without_duplicates(deals_client):
    client, all_deals = deals_client
    page_size = 25
    seen_ids: list[str] = []
    cursor = None
    body = None

    while True:
        params = {"limit": page_size}
        if cursor:
            params["before"] = cursor
        r = client.get("/api/deals", params=params)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert body["items"] == body["deals"]
        page_ids = [d["id"] for d in body["items"]]
        assert len(set(page_ids)) == len(page_ids)
        overlap = set(page_ids) & set(seen_ids)
        assert not overlap, f"duplicate ids across pages: {overlap}"
        seen_ids.extend(page_ids)
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == 60
    assert set(seen_ids) == {d["id"] for d in all_deals}
    assert body["metrics"]["open_count"] == 60


def test_deals_limit_capped_at_200():
    async def mock_principal():
        return MOCK_PRINCIPAL

    server.app.dependency_overrides[server.get_principal] = mock_principal
    deals = _make_deals(5)
    mock_db = type("DB", (), {})()
    mock_db.deals = FakeCollection(deals, "updated_at")
    mock_db.activities = FakeCollection([], "created_at")

    with patch.object(server, "db", mock_db):
        client = TestClient(server.app)
        r = client.get("/api/deals", params={"limit": 500})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 5
    server.app.dependency_overrides.clear()
