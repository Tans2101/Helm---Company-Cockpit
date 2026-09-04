"""Production chain API tests."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_production_chain")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402

CEO = {
    "user_id": "u_ceo",
    "email": "ceo@acme.com",
    "name": "CEO",
    "workspace_id": "ws_test",
    "role": "owner",
    "pack": "owner",
}

OUTSIDER = {
    "user_id": "u_out",
    "email": "out@acme.com",
    "name": "Out",
    "workspace_id": "ws_test",
    "role": "member",
    "pack": "member",
}

MEMBER = {
    "user_id": "u_mem",
    "email": "mem@acme.com",
    "name": "Mem",
    "workspace_id": "ws_test",
    "role": "member",
    "pack": "member",
}

PROD_DEPT = {
    "department_id": "dept_prod",
    "workspace_id": "ws_test",
    "type": "production",
    "name": "Production",
    "enabled": True,
}


class StageStore:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                return {k: v for k, v in r.items() if k != "_id"}
        return None

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if all(r.get(k) == v for k, v in query.items())]
        state = {"sort": None}

        class C:
            def sort(self, field, direction=1):
                state["sort"] = (field, direction)
                return self

            async def to_list(self, n):
                items = list(matched)
                if state["sort"]:
                    field, direction = state["sort"]
                    items.sort(key=lambda x: x.get(field, 0), reverse=direction == -1)
                return items[:n]

        return C()

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def update_one(self, query, update):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                r.update(update.get("$set") or {})
                return

    async def delete_one(self, query):
        before = len(self.rows)
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]
        return MagicMock(deleted_count=before - len(self.rows))


@pytest.fixture
def prod_api():
    stages = StageStore()
    dept_members = [
        {"department_id": "dept_prod", "user_id": "u_mem", "role": "member"},
        {"department_id": "dept_prod", "user_id": "u_lead", "role": "lead"},
    ]

    async def dept_find_one(query, projection=None):
        if query.get("type") == "production" or query.get("department_id") == "dept_prod":
            if query.get("workspace_id") in (None, "ws_test") or query.get("workspace_id") == "ws_test":
                if "enabled" in query and not PROD_DEPT.get("enabled"):
                    return None
                return dict(PROD_DEPT)
        return None

    async def mem_find_one(query, projection=None):
        for m in dept_members:
            if all(m.get(k) == v for k, v in query.items()):
                return dict(m)
        return None

    mock_db = MagicMock()
    mock_db.departments.find_one = AsyncMock(side_effect=dept_find_one)
    mock_db.department_members.find_one = AsyncMock(side_effect=mem_find_one)
    mock_db.production_stages = stages
    mock_db.users.find_one = AsyncMock(return_value={"name": "Mem", "email": "mem@acme.com", "picture": None})

    async def as_ceo():
        return CEO

    async def as_outsider():
        return OUTSIDER

    async def as_member():
        return MEMBER

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db):
        client = TestClient(server.app)
        yield client, stages, as_ceo, as_outsider, as_member
    server.app.dependency_overrides.clear()


def test_outsider_gets_403(prod_api):
    client, stages, as_ceo, as_outsider, as_member = prod_api
    server.app.dependency_overrides[server.get_principal] = as_outsider
    assert client.get("/api/production/stages").status_code == 403
    assert client.post("/api/production/stages", json={"name": "Cut"}).status_code == 403


def test_ceo_create_list_reorder_delete(prod_api):
    client, stages, as_ceo, as_outsider, as_member = prod_api
    r = client.post("/api/production/stages", json={"name": "Prep"})
    assert r.status_code == 200, r.text
    sid1 = r.json()["stage"]["id"]
    r2 = client.post("/api/production/stages", json={"name": "Assemble"})
    sid2 = r2.json()["stage"]["id"]

    listed = client.get("/api/production/stages").json()["stages"]
    assert [s["name"] for s in listed] == ["Prep", "Assemble"]

    rr = client.patch("/api/production/stages/reorder", json={"stage_ids": [sid2, sid1]})
    assert rr.status_code == 200, rr.text
    listed2 = client.get("/api/production/stages").json()["stages"]
    assert [s["name"] for s in listed2] == ["Assemble", "Prep"]

    assert client.delete(f"/api/production/stages/{sid2}").status_code == 200
    left = client.get("/api/production/stages").json()["stages"]
    assert [s["name"] for s in left] == ["Prep"]
    assert left[0]["order"] == 0


def test_member_can_update_status_not_name(prod_api):
    client, stages, as_ceo, as_outsider, as_member = prod_api
    sid = client.post("/api/production/stages", json={"name": "QA"}).json()["stage"]["id"]
    server.app.dependency_overrides[server.get_principal] = as_member
    ok = client.patch(f"/api/production/stages/{sid}", json={"status": "in_progress", "assigned_user_ids": ["u_mem"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["stage"]["status"] == "in_progress"
    assert "u_mem" in ok.json()["stage"]["assigned_user_ids"]

    denied = client.patch(f"/api/production/stages/{sid}", json={"name": "Renamed"})
    assert denied.status_code == 403

    assert client.post("/api/production/stages", json={"name": "X"}).status_code == 403
    assert client.delete(f"/api/production/stages/{sid}").status_code == 403
