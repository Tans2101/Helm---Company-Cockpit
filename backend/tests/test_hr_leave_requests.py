"""HR leave / time-off request API + calendar range visibility."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_hr_leave")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from mongo_mocks import attach_users_in_find  # noqa: E402

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

HR_DEPT = {
    "department_id": "dept_hr",
    "workspace_id": "ws_test",
    "type": "hr",
    "name": "HR",
    "enabled": True,
}


def _match(doc: dict, query: dict) -> bool:
    if not query:
        return True
    for k, v in query.items():
        if isinstance(v, dict):
            if "$exists" in v:
                if v["$exists"] and k not in doc:
                    return False
                if (not v["$exists"]) and k in doc:
                    return False
            if "$nin" in v and doc.get(k) in v["$nin"]:
                return False
            if "$in" in v and doc.get(k) not in v["$in"]:
                return False
            continue
        if doc.get(k) != v:
            return False
    return True


class CollStore:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if _match(r, query or {}):
                return {k: v for k, v in r.items() if k != "_id"}
        return None

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if _match(r, query or {})]

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
            if _match(r, query or {}):
                r.update(update.get("$set") or {})
                return MagicMock(matched_count=1)
        return MagicMock(matched_count=0)


@pytest.fixture
def leave_api():
    employees = CollStore([
        {
            "id": "hremp_ada",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "Ada Lovelace",
            "status": "active",
            "linked_user_id": "u_mem",
        },
        {
            "id": "hremp_bob",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "Bob",
            "status": "active",
            "linked_user_id": "u_other",
        },
    ])
    leaves = CollStore()
    depts = MagicMock()
    depts.find_one = AsyncMock(return_value=dict(HR_DEPT))
    members = MagicMock()

    async def member_find_one(query, projection=None):
        uid = query.get("user_id")
        roles = {"u_mem": "member", "u_lead": "lead"}
        if uid in roles:
            return {"department_id": "dept_hr", "user_id": uid, "role": roles[uid]}
        return None

    members.find_one = AsyncMock(side_effect=member_find_one)
    users = MagicMock()
    users.find_one = AsyncMock(return_value={"name": "Mem", "email": "mem@acme.com"})
    attach_users_in_find(users)

    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.hr_employees = employees
    mock_db.hr_leave_requests = leaves
    mock_db.users = users

    async def as_ceo():
        return CEO

    async def as_member():
        return MEMBER

    async def as_lead():
        return LEAD

    server.app.dependency_overrides[server.get_principal] = as_lead
    with patch.object(server, "db", mock_db), \
         patch.object(server, "BILLING_ENFORCED", False):
        client = TestClient(server.app)
        yield client, employees, leaves, as_ceo, as_member, as_lead, mock_db
    server.app.dependency_overrides.clear()


def test_member_can_create_for_linked_employee_not_others(leave_api):
    client, employees, leaves, as_ceo, as_member, as_lead, mock_db = leave_api
    server.app.dependency_overrides[server.get_principal] = as_member

    ok = client.post("/api/hr/leave-requests", json={
        "employee_id": "hremp_ada",
        "type": "vacation",
        "start_date": "2026-09-20",
        "end_date": "2026-09-22",
        "note": "Trip",
    })
    assert ok.status_code == 200, ok.text
    assert leaves.rows[0]["status"] == "pending"
    assert leaves.rows[0]["requested_by"] == "u_mem"
    assert leaves.rows[0]["title"].startswith("Ada Lovelace")

    denied = client.post("/api/hr/leave-requests", json={
        "employee_id": "hremp_bob",
        "type": "sick",
        "start_date": "2026-09-20",
        "end_date": "2026-09-20",
    })
    assert denied.status_code == 403


def test_member_cannot_approve(leave_api):
    client, employees, leaves, as_ceo, as_member, as_lead, mock_db = leave_api
    leaves.rows.append({
        "id": "hrleave_1",
        "department_id": "dept_hr",
        "employee_id": "hremp_ada",
        "status": "pending",
        "start_date": "2026-09-20",
        "end_date": "2026-09-22",
        "type": "vacation",
        "title": "Ada Lovelace — Vacation",
    })
    server.app.dependency_overrides[server.get_principal] = as_member
    r = client.patch("/api/hr/leave-requests/hrleave_1", json={"status": "approved"})
    assert r.status_code == 403
    assert leaves.rows[0]["status"] == "pending"


def test_lead_can_approve_and_deny(leave_api):
    client, employees, leaves, as_ceo, as_member, as_lead, mock_db = leave_api
    leaves.rows.append({
        "id": "hrleave_1",
        "department_id": "dept_hr",
        "employee_id": "hremp_ada",
        "employee_name": "Ada Lovelace",
        "status": "pending",
        "start_date": "2026-09-20",
        "end_date": "2026-09-22",
        "type": "vacation",
        "title": "Ada Lovelace — Vacation",
        "workspace_id": "ws_test",
    })
    r = client.patch("/api/hr/leave-requests/hrleave_1", json={"status": "approved"})
    assert r.status_code == 200, r.text
    assert leaves.rows[0]["status"] == "approved"
    assert leaves.rows[0]["decided_by"] == "u_lead"

    leaves.rows.append({
        "id": "hrleave_2",
        "department_id": "dept_hr",
        "employee_id": "hremp_ada",
        "status": "pending",
        "start_date": "2026-10-01",
        "end_date": "2026-10-01",
        "type": "personal",
        "title": "Ada Lovelace — Personal",
        "workspace_id": "ws_test",
    })
    r2 = client.patch("/api/hr/leave-requests/hrleave_2", json={"status": "denied"})
    assert r2.status_code == 200
    assert leaves.rows[1]["status"] == "denied"


def test_list_filters(leave_api):
    client, employees, leaves, *_ = leave_api
    leaves.rows.extend([
        {
            "id": "a", "department_id": "dept_hr", "employee_id": "hremp_ada",
            "status": "pending", "start_date": "2026-09-20", "end_date": "2026-09-20",
        },
        {
            "id": "b", "department_id": "dept_hr", "employee_id": "hremp_bob",
            "status": "approved", "start_date": "2026-09-21", "end_date": "2026-09-21",
        },
    ])
    all_r = client.get("/api/hr/leave-requests")
    assert len(all_r.json()["requests"]) == 2
    pending = client.get("/api/hr/leave-requests", params={"status": "pending"})
    assert [r["id"] for r in pending.json()["requests"]] == ["a"]
    by_emp = client.get("/api/hr/leave-requests", params={"employee_id": "hremp_bob"})
    assert [r["id"] for r in by_emp.json()["requests"]] == ["b"]


@pytest.mark.asyncio
async def test_approved_leave_spans_calendar_range(leave_api):
    client, employees, leaves, as_ceo, as_member, as_lead, mock_db = leave_api
    leaves.rows.extend([
        {
            "id": "hrleave_ok",
            "workspace_id": "ws_test",
            "department_id": "dept_hr",
            "employee_id": "hremp_ada",
            "title": "Ada Lovelace — Vacation",
            "start_date": "2026-09-15",
            "end_date": "2026-09-17",
            "status": "approved",
            "type": "vacation",
        },
        {
            "id": "hrleave_pending",
            "workspace_id": "ws_test",
            "department_id": "dept_hr",
            "employee_id": "hremp_ada",
            "title": "Ada Lovelace — Sick",
            "start_date": "2026-09-15",
            "end_date": "2026-09-16",
            "status": "pending",
            "type": "sick",
        },
        {
            "id": "hrleave_denied",
            "workspace_id": "ws_test",
            "department_id": "dept_hr",
            "employee_id": "hremp_ada",
            "title": "Ada Lovelace — Personal",
            "start_date": "2026-09-15",
            "end_date": "2026-09-16",
            "status": "denied",
            "type": "personal",
        },
    ])
    # departments.find_one used by get_enabled_department — MagicMock depts already
    # returns HR_DEPT for any find_one; also need type-aware lookup for calendar.
    async def dept_find_one(query, projection=None):
        if query.get("type") == "hr" or query.get("department_id") == "dept_hr":
            return dict(HR_DEPT)
        return None

    mock_db.departments.find_one = AsyncMock(side_effect=dept_find_one)

    with patch.object(server, "db", mock_db):
        rows = await server._department_calendar_upcoming("ws_test")

    by_id = {r["id"]: r for r in rows}
    assert "hrleave_ok" in by_id
    assert by_id["hrleave_ok"]["date"] == "2026-09-15"
    assert by_id["hrleave_ok"]["end_date"] == "2026-09-17"
    assert by_id["hrleave_ok"]["type"] == "Leave"
    assert by_id["hrleave_ok"]["source_type"] == "hr_leave_request"
    assert "hrleave_pending" not in by_id
    assert "hrleave_denied" not in by_id

    events = server._deadlines_as_events([by_id["hrleave_ok"]])
    assert events[0]["start_at"].startswith("2026-09-15")
    assert events[0]["end_at"].startswith("2026-09-17")
    assert events[0]["all_day"] is True

    # Range overlapping week starting Sunday 2026-09-13 includes mid-week leave
    assert server._upcoming_overlaps_week(by_id["hrleave_ok"], "2026-09-13", "2026-09-19")
    # Leave entirely after week should not overlap
    assert not server._upcoming_overlaps_week(
        {"date": "2026-09-22", "end_date": "2026-09-24"},
        "2026-09-13",
        "2026-09-19",
    )


def test_leave_source_in_calendar_registry():
    leave = next(s for s in server.CALENDAR_DATE_SOURCES if s["collection"] == "hr_leave_requests")
    assert leave["date_field"] == "start_date"
    assert leave["end_date_field"] == "end_date"
    assert leave["open_statuses"] == frozenset({"approved"})
    # Existing single-day sources unchanged
    for coll in ("production_work_orders", "procurement_requests", "legal_matters"):
        src = next(s for s in server.CALENDAR_DATE_SOURCES if s["collection"] == coll)
        assert "end_date_field" not in src
