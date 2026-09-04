"""Engineering & Maintenance ticket queue API tests."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_maintenance_tickets")

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

TECH = {
    "user_id": "u_tech",
    "email": "tech@acme.com",
    "name": "Tech",
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

MAINT_DEPT = {
    "department_id": "dept_maint",
    "workspace_id": "ws_test",
    "type": "engineering_maintenance",
    "name": "Engineering & Maintenance",
    "enabled": True,
}


class TicketStore:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                return {k: v for k, v in r.items() if k != "_id"}
        return None

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if all(r.get(k) == v for k, v in query.items())]

        class C:
            async def to_list(self, n):
                return matched[:n]

            def sort(self, *a, **k):
                return self

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
def maint_api():
    store = TicketStore()
    depts = MagicMock()
    depts.find_one = AsyncMock(return_value=dict(MAINT_DEPT))
    members = MagicMock()

    async def member_find_one(query, projection=None):
        uid = query.get("user_id")
        roles = {"u_mem": "member", "u_tech": "member", "u_lead": "lead"}
        if uid in roles:
            return {"department_id": "dept_maint", "user_id": uid, "role": roles[uid]}
        return None

    members.find_one = AsyncMock(side_effect=member_find_one)
    users = MagicMock()
    users.find_one = AsyncMock(return_value={"name": "Mem", "email": "mem@acme.com"})

    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.maintenance_tickets = store
    mock_db.users = users

    async def as_ceo():
        return CEO

    async def as_member():
        return MEMBER

    async def as_tech():
        return TECH

    async def as_lead():
        return LEAD

    async def as_outsider():
        return OUTSIDER

    server.app.dependency_overrides[server.get_principal] = as_member
    with patch.object(server, "db", mock_db), \
         patch.object(server, "BILLING_ENFORCED", False):
        client = TestClient(server.app)
        yield client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts
    server.app.dependency_overrides.clear()


def test_maint_not_placeholder():
    assert catalog.TYPE_ENGINEERING_MAINTENANCE not in catalog.PLACEHOLDER_SHELL_TYPES


def test_outsider_403(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    server.app.dependency_overrides[server.get_principal] = as_outsider
    assert client.get("/api/maintenance/tickets").status_code == 403
    assert client.post("/api/maintenance/tickets", json={"equipment_name": "Pump"}).status_code == 403


def test_create_sets_reported_by_unassigned(maint_api):
    client, store, *_ = maint_api
    r = client.post("/api/maintenance/tickets", json={
        "equipment_name": "CNC #3",
        "description": "Bearing noise",
        "priority": "high",
        "reported_by": "u_hacker",
        "assigned_technician": "u_tech",
    })
    assert r.status_code == 200, r.text
    body = r.json()["ticket"]
    assert body["reported_by"] == "u_mem"
    assert body["assigned_technician"] is None
    assert body["status"] == "reported"
    assert body["priority"] == "high"


def test_member_cannot_assign(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    client.post("/api/maintenance/tickets", json={"equipment_name": "Lathe"})
    tid = store.rows[0]["id"]
    r = client.patch(f"/api/maintenance/tickets/{tid}", json={"assigned_technician": "u_tech"})
    assert r.status_code == 403


def test_lead_assigns_then_tech_updates(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    client.post("/api/maintenance/tickets", json={"equipment_name": "Lathe", "priority": "medium"})
    tid = store.rows[0]["id"]
    server.app.dependency_overrides[server.get_principal] = as_lead
    r = client.patch(f"/api/maintenance/tickets/{tid}", json={"assigned_technician": "u_tech"})
    assert r.status_code == 200
    assert store.rows[0]["assigned_technician"] == "u_tech"

    server.app.dependency_overrides[server.get_principal] = as_tech
    r2 = client.patch(f"/api/maintenance/tickets/{tid}", json={
        "status": "in_repair",
        "notes": "Parts ordered",
    })
    assert r2.status_code == 200, r2.text
    assert store.rows[0]["status"] == "in_repair"
    assert store.rows[0]["notes"] == "Parts ordered"


def test_non_assignee_cannot_update(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    client.post("/api/maintenance/tickets", json={"equipment_name": "Lathe"})
    store.rows[0]["assigned_technician"] = "u_tech"
    tid = store.rows[0]["id"]
    r = client.patch(f"/api/maintenance/tickets/{tid}", json={"notes": "nope"})
    assert r.status_code == 403


def test_sort_open_high_first(maint_api):
    client, store, *_ = maint_api
    store.rows = [
        {"id": "1", "department_id": "dept_maint", "equipment_name": "A", "priority": "low",
         "status": "reported", "created_at": "2026-01-03"},
        {"id": "2", "department_id": "dept_maint", "equipment_name": "B", "priority": "high",
         "status": "resolved", "created_at": "2026-01-04"},
        {"id": "3", "department_id": "dept_maint", "equipment_name": "C", "priority": "high",
         "status": "reported", "created_at": "2026-01-01"},
        {"id": "4", "department_id": "dept_maint", "equipment_name": "D", "priority": "medium",
         "status": "diagnosed", "created_at": "2026-01-02"},
    ]
    r = client.get("/api/maintenance/tickets")
    assert r.status_code == 200
    names = [t["equipment_name"] for t in r.json()["tickets"]]
    # unresolved first: C (high), D (medium), A (low), then resolved B
    assert names == ["C", "D", "A", "B"]


def test_filter_status_priority(maint_api):
    client, store, *_ = maint_api
    client.post("/api/maintenance/tickets", json={"equipment_name": "A", "priority": "high"})
    client.post("/api/maintenance/tickets", json={"equipment_name": "B", "priority": "low"})
    store.rows[0]["status"] = "resolved"
    r = client.get("/api/maintenance/tickets?status=resolved&priority=high")
    assert r.status_code == 200
    assert len(r.json()["tickets"]) == 1
    assert r.json()["tickets"][0]["equipment_name"] == "A"


def test_independent_tickets(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    client.post("/api/maintenance/tickets", json={"equipment_name": "A"})
    client.post("/api/maintenance/tickets", json={"equipment_name": "B"})
    store.rows[0]["assigned_technician"] = "u_mem"
    store.rows[1]["assigned_technician"] = "u_mem"
    a, b = store.rows[0]["id"], store.rows[1]["id"]
    client.patch(f"/api/maintenance/tickets/{a}", json={"status": "diagnosed"})
    assert store.rows[0]["status"] == "diagnosed"
    assert store.rows[1]["status"] == "reported"


def test_delete_lead_only(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    client.post("/api/maintenance/tickets", json={"equipment_name": "A"})
    tid = store.rows[0]["id"]
    assert client.delete(f"/api/maintenance/tickets/{tid}").status_code == 403
    server.app.dependency_overrides[server.get_principal] = as_lead
    assert client.delete(f"/api/maintenance/tickets/{tid}").status_code == 200
    assert store.rows == []


def test_lead_can_assign_on_create(maint_api):
    client, store, as_ceo, as_member, as_tech, as_lead, as_outsider, depts = maint_api
    server.app.dependency_overrides[server.get_principal] = as_lead
    r = client.post("/api/maintenance/tickets", json={
        "equipment_name": "Press",
        "assigned_technician": "u_tech",
    })
    assert r.status_code == 200
    assert store.rows[0]["assigned_technician"] == "u_tech"
    assert store.rows[0]["reported_by"] == "u_lead"
