"""Procurement request queue API tests."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_procurement_queue")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
import departments_catalog as catalog  # noqa: E402

CEO = {
    "user_id": "u_ceo",
    "email": "ceo@acme.com",
    "name": "CEO",
    "workspace_id": "ws_test",
    "role": "owner",
    "pack": "owner",
}

LEAD = {
    "user_id": "u_lead",
    "email": "lead@acme.com",
    "name": "Lead",
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

OUTSIDER = {
    "user_id": "u_out",
    "email": "out@acme.com",
    "name": "Out",
    "workspace_id": "ws_test",
    "role": "member",
    "pack": "member",
}

PROC_DEPT = {
    "department_id": "dept_proc",
    "workspace_id": "ws_test",
    "type": "procurement",
    "name": "Procurement",
    "enabled": True,
}


class RequestStore:
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
                    items.sort(
                        key=lambda x: x.get(field) or "",
                        reverse=direction == -1,
                    )
                return items[:n]

        return C()

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def update_one(self, query, update):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                r.update(update.get("$set") or {})
                return MagicMock(matched_count=1)
        return MagicMock(matched_count=0)

    async def delete_one(self, query):
        before = len(self.rows)
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]
        return MagicMock(deleted_count=before - len(self.rows))


@pytest.fixture
def proc_api():
    store = RequestStore()
    depts = MagicMock()
    depts.find_one = AsyncMock(return_value=dict(PROC_DEPT))
    members = MagicMock()

    async def member_find_one(query, projection=None):
        uid = query.get("user_id")
        if uid == "u_mem":
            return {"department_id": "dept_proc", "user_id": "u_mem", "role": "member"}
        if uid == "u_lead":
            return {"department_id": "dept_proc", "user_id": "u_lead", "role": "lead"}
        if uid == "u_ceo":
            return None  # CEO bypasses membership
        return None

    members.find_one = AsyncMock(side_effect=member_find_one)
    users = MagicMock()
    users.find_one = AsyncMock(return_value={"name": "Mem", "email": "mem@acme.com"})

    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.procurement_requests = store
    mock_db.users = users

    async def as_ceo():
        return CEO

    async def as_member():
        return MEMBER

    async def as_lead():
        return LEAD

    async def as_outsider():
        return OUTSIDER

    server.app.dependency_overrides[server.get_principal] = as_member
    with patch.object(server, "db", mock_db), \
         patch.object(server, "BILLING_ENFORCED", False):
        client = TestClient(server.app)
        yield client, store, as_ceo, as_member, as_lead, as_outsider, depts
    server.app.dependency_overrides.clear()


def test_procurement_not_placeholder():
    assert catalog.TYPE_PROCUREMENT not in catalog.PLACEHOLDER_SHELL_TYPES


def test_outsider_gets_403(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    server.app.dependency_overrides[server.get_principal] = as_outsider
    assert client.get("/api/procurement/requests").status_code == 403
    assert client.post("/api/procurement/requests", json={"item": "Bolts", "quantity": 10}).status_code == 403


def test_member_creates_with_server_requested_by(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    r = client.post("/api/procurement/requests", json={
        "item": "Steel plate",
        "quantity": 4,
        "vendor_name": "Acme Metals",
        "requested_by": "u_hacker",  # ignored — not on model
    })
    assert r.status_code == 200, r.text
    body = r.json()["request"]
    assert body["requested_by"] == "u_mem"
    assert body["status"] == "requested"
    assert body["item"] == "Steel plate"
    assert store.rows[0]["requested_by"] == "u_mem"


def test_member_cannot_approve(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "Widget", "quantity": 1})
    rid = store.rows[0]["id"]
    r = client.patch(f"/api/procurement/requests/{rid}", json={"status": "approved"})
    assert r.status_code == 403
    assert store.rows[0]["status"] == "requested"


def test_member_can_edit_own_requested(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "Widget", "quantity": 1})
    rid = store.rows[0]["id"]
    r = client.patch(f"/api/procurement/requests/{rid}", json={
        "item": "Widget v2", "quantity": 3, "vendor_name": "V", "notes": "rush",
    })
    assert r.status_code == 200, r.text
    assert store.rows[0]["item"] == "Widget v2"
    assert store.rows[0]["quantity"] == 3.0


def test_lead_approves_sets_approved_by(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "Cable", "quantity": 2})
    rid = store.rows[0]["id"]
    server.app.dependency_overrides[server.get_principal] = as_lead
    r = client.patch(f"/api/procurement/requests/{rid}", json={"status": "approved"})
    assert r.status_code == 200, r.text
    assert store.rows[0]["status"] == "approved"
    assert store.rows[0]["approved_by"] == "u_lead"


def test_ceo_can_reject(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "Cable", "quantity": 2})
    rid = store.rows[0]["id"]
    server.app.dependency_overrides[server.get_principal] = as_ceo
    r = client.patch(f"/api/procurement/requests/{rid}", json={"status": "rejected"})
    assert r.status_code == 200
    assert store.rows[0]["status"] == "rejected"


def test_independent_statuses(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "A", "quantity": 1})
    client.post("/api/procurement/requests", json={"item": "B", "quantity": 1})
    a, b = store.rows[0]["id"], store.rows[1]["id"]
    server.app.dependency_overrides[server.get_principal] = as_lead
    client.patch(f"/api/procurement/requests/{a}", json={"status": "approved"})
    assert store.rows[0]["status"] == "approved"
    assert store.rows[1]["status"] == "requested"


def test_list_filter_by_status(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "A", "quantity": 1})
    client.post("/api/procurement/requests", json={"item": "B", "quantity": 1})
    store.rows[0]["status"] = "delivered"
    r = client.get("/api/procurement/requests?status=delivered")
    assert r.status_code == 200
    assert len(r.json()["requests"]) == 1
    assert r.json()["requests"][0]["item"] == "A"


def test_member_delete_own_requested(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "Temp", "quantity": 1})
    rid = store.rows[0]["id"]
    r = client.delete(f"/api/procurement/requests/{rid}")
    assert r.status_code == 200
    assert store.rows == []


def test_member_cannot_delete_after_approve(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    client.post("/api/procurement/requests", json={"item": "Temp", "quantity": 1})
    rid = store.rows[0]["id"]
    store.rows[0]["status"] = "approved"
    r = client.delete(f"/api/procurement/requests/{rid}")
    assert r.status_code == 403
    assert len(store.rows) == 1


def test_dept_disabled_404(proc_api):
    client, store, as_ceo, as_member, as_lead, as_outsider, depts = proc_api
    depts.find_one = AsyncMock(return_value=None)
    assert client.get("/api/procurement/requests").status_code == 404
