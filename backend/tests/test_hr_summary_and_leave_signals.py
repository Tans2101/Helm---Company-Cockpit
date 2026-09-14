"""HR summary stats + pending leave Decision Center signals."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_hr_summary_signals")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import decision_engine as eng  # noqa: E402
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
def summary_api():
    now = datetime.now(timezone.utc)
    employees = CollStore([
        {
            "id": "hremp_a",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "Active One",
            "status": "active",
        },
        {
            "id": "hremp_b",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "Active Two",
            "status": "active",
        },
        {
            "id": "hremp_c",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "On Leave",
            "status": "on_leave",
        },
        {
            "id": "hremp_d",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "Recent Departure",
            "status": "departed",
            "departed_at": (now - timedelta(days=30)).isoformat(),
        },
        {
            "id": "hremp_e",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "name": "Old Departure",
            "status": "departed",
            "departed_at": (now - timedelta(days=120)).isoformat(),
        },
    ])
    leaves = CollStore([
        {
            "id": "hrleave_pending",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "employee_id": "hremp_a",
            "employee_name": "Active One",
            "status": "pending",
            "created_at": (now - timedelta(days=2)).isoformat(),
            "updated_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "id": "hrleave_approved",
            "department_id": "dept_hr",
            "workspace_id": "ws_test",
            "employee_id": "hremp_b",
            "employee_name": "Active Two",
            "status": "approved",
            "created_at": (now - timedelta(days=5)).isoformat(),
            "updated_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "id": "hrleave_other_dept",
            "department_id": "dept_other",
            "workspace_id": "ws_other",
            "status": "pending",
        },
    ])
    depts = MagicMock()
    depts.find_one = AsyncMock(return_value=dict(HR_DEPT))
    members = MagicMock()
    members.find_one = AsyncMock(return_value=None)
    users = MagicMock()
    users.find_one = AsyncMock(return_value={"name": "CEO", "email": "ceo@acme.com"})
    attach_users_in_find(users)

    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.hr_employees = employees
    mock_db.hr_leave_requests = leaves
    mock_db.hr_records = CollStore([{"id": "secret", "ssn": "should-never-appear"}])
    mock_db.users = users

    async def as_ceo():
        return CEO

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db), \
         patch.object(server, "BILLING_ENFORCED", False):
        client = TestClient(server.app)
        yield client, mock_db, now
    server.app.dependency_overrides.clear()


def test_hr_summary_counts_status_pending_and_recent_departures(summary_api):
    client, mock_db, _now = summary_api
    r = client.get("/api/hr/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["headcount"] == {"active": 2, "on_leave": 1, "departed": 2}
    assert body["pending_leave_requests"] == 1
    assert body["departed_last_90_days"] == 1
    # Confidentiality: never surface hr_records
    blob = str(body).lower()
    assert "ssn" not in blob
    assert "hr_records" not in blob
    assert "secret" not in blob


def test_detect_pending_leave_requests_stale_vs_fresh():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    requests = [
        {
            "id": "lr_stale",
            "status": "pending",
            "employee_name": "Ada Lovelace",
            "employee_id": "hremp_ada",
            "updated_at": (now - timedelta(days=4)).isoformat(),
            "created_at": (now - timedelta(days=4)).isoformat(),
        },
        {
            "id": "lr_fresh",
            "status": "pending",
            "employee_name": "Bob",
            "updated_at": (now - timedelta(days=1)).isoformat(),
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "id": "lr_decided",
            "status": "approved",
            "employee_name": "Cara",
            "updated_at": (now - timedelta(days=10)).isoformat(),
            "created_at": (now - timedelta(days=10)).isoformat(),
        },
    ]
    sigs = eng.detect_pending_leave_requests(requests, stale_days=3, now=now)
    assert len(sigs) == 1
    assert sigs[0]["related_id"] == "lr_stale"
    assert sigs[0]["type"] == "pending_leave_request"
    assert sigs[0]["severity"] == "medium"
    assert sigs[0]["summary"] == "Leave request from Ada Lovelace has been pending 4 days."
    assert "pending_leave_request" in eng.DECISION_SIGNAL_TYPES
    blob = (sigs[0]["summary"] + " " + sigs[0]["detail"]).lower()
    for banned in ("should", "must", "recommend", "advise", "consider"):
        assert banned not in blob


def test_collect_department_signals_includes_stale_leave_for_hr():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    spec = eng.SPEC_BY_TYPE["hr"]
    bundles = [{
        "spec": spec,
        "items": [],
        "leave_requests": [
            {
                "id": "lr_old",
                "status": "pending",
                "employee_name": "Jordan",
                "updated_at": (now - timedelta(days=5)).isoformat(),
            },
            {
                "id": "lr_ok",
                "status": "pending",
                "employee_name": "Sam",
                "updated_at": (now - timedelta(hours=12)).isoformat(),
            },
        ],
    }]
    sigs = eng.collect_department_signals(bundles, now=now)
    leave_sigs = [s for s in sigs if s["type"] == "pending_leave_request"]
    assert len(leave_sigs) == 1
    assert leave_sigs[0]["related_id"] == "lr_old"
    assert "Jordan" in leave_sigs[0]["summary"]


@pytest.mark.asyncio
async def test_department_signal_inputs_loads_leave_when_hr_enabled():
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    leave_rows = [{
        "id": "lr1",
        "workspace_id": "ws_test",
        "status": "pending",
        "employee_name": "Ada",
        "updated_at": (now - timedelta(days=4)).isoformat(),
    }]

    class Coll:
        def __init__(self, rows):
            self.rows = rows

        def find(self, query, projection=None):
            matched = [dict(r) for r in self.rows if all(r.get(k) == v for k, v in query.items())]
            cursor = MagicMock()
            cursor.to_list = AsyncMock(return_value=matched)
            return cursor

    mock_db = MagicMock()
    mock_db.production_work_orders = Coll([])
    mock_db.legal_matters = Coll([])
    mock_db.procurement_requests = Coll([])
    mock_db.maintenance_tickets = Coll([])
    mock_db.hr_onboarding_instances = Coll([])
    mock_db.hr_leave_requests = Coll(leave_rows)

    async def enabled(_db, workspace_id, dept_type):
        if dept_type == "hr":
            return {"department_id": "dept_hr", "type": "hr", "enabled": True}
        return None

    with patch.object(server, "db", mock_db), \
         patch.object(server.dept_migrate, "get_enabled_department", side_effect=enabled):
        bundles = await server._department_signal_inputs("ws_test")

    assert len(bundles) == 1
    assert bundles[0]["spec"]["type"] == "hr"
    assert bundles[0]["leave_requests"][0]["id"] == "lr1"

    signals = eng.collect_department_signals(bundles, now=now)
    assert any(s["type"] == "pending_leave_request" for s in signals)
