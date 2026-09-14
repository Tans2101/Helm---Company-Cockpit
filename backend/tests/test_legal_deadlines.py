"""Legal matter due_date: API, calendar registry, and deadline signals."""
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_legal_deadlines")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import decision_engine as eng  # noqa: E402
import server  # noqa: E402
import departments_catalog as catalog  # noqa: E402
from mongo_mocks import attach_users_in_find  # noqa: E402


CEO = {
    "user_id": "u_ceo",
    "email": "ceo@acme.com",
    "name": "CEO",
    "workspace_id": "ws_legal_due",
    "role": "owner",
    "pack": "owner",
}

LEGAL_DEPT = {
    "department_id": "dept_legal",
    "workspace_id": "ws_legal_due",
    "type": catalog.TYPE_LEGAL,
    "name": "Legal",
    "enabled": True,
}


def _match(doc: dict, query: dict) -> bool:
    if not query:
        return True
    for k, v in query.items():
        if isinstance(v, dict):
            if "$in" in v and doc.get(k) not in v["$in"]:
                return False
            if "$nin" in v and doc.get(k) in v["$nin"]:
                return False
            if "$exists" in v:
                exists = k in doc and doc.get(k) is not None
                if bool(v["$exists"]) != exists:
                    return False
            continue
        if doc.get(k) != v:
            return False
    return True


class MatterStore:
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
            def sort(self, *a, **k):
                return self

            async def to_list(self, n):
                return matched[:n]

        return C()

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return MagicMock()

    async def update_one(self, query, update):
        for r in self.rows:
            if _match(r, query or {}):
                r.update(update.get("$set") or {})
                return MagicMock(matched_count=1)
        return MagicMock(matched_count=0)


@pytest.fixture
def legal_api():
    store = MatterStore()
    depts = MagicMock()
    depts.find_one = AsyncMock(return_value=dict(LEGAL_DEPT))
    members = MagicMock()
    members.find_one = AsyncMock(return_value={
        "department_id": "dept_legal", "user_id": "u_ceo", "role": "lead",
    })
    users = MagicMock()
    users.find_one = AsyncMock(return_value={
        "user_id": "u_ceo", "name": "CEO", "email": "ceo@acme.com",
    })
    attach_users_in_find(users)

    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.legal_matters = store
    mock_db.users = users

    async def as_ceo():
        return CEO

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db), \
         patch.object(server, "BILLING_ENFORCED", False):
        yield TestClient(server.app), store
    server.app.dependency_overrides.clear()


def test_create_and_patch_due_date(legal_api):
    client, store = legal_api
    r = client.post("/api/legal/matters", json={
        "title": "Business license renewal",
        "matter_type": "compliance",
        "due_date": "2026-09-21",
    })
    assert r.status_code == 200, r.text
    matter = r.json()["matter"]
    assert matter["due_date"] == "2026-09-21"
    assert store.rows[0]["due_date"] == "2026-09-21"

    r2 = client.patch(f"/api/legal/matters/{matter['id']}", json={"due_date": "2026-10-01"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["matter"]["due_date"] == "2026-10-01"

    bad = client.post("/api/legal/matters", json={
        "title": "Bad date",
        "due_date": "next week",
    })
    assert bad.status_code == 400


def test_detect_upcoming_and_overdue_legal_deadlines():
    today = date(2026, 9, 14)
    matters = [
        {
            "id": "m1",
            "title": "State license",
            "matter_type": "compliance",
            "status": "internal_review",
            "due_date": "2026-09-19",
        },
        {
            "id": "m2",
            "title": "Vendor MSA",
            "matter_type": "contract",
            "status": "draft",
            "due_date": "2026-09-01",
        },
        {
            "id": "m3",
            "title": "Already filed",
            "matter_type": "compliance",
            "status": "filed",
            "due_date": "2026-09-10",
        },
        {
            "id": "m4",
            "title": "Far out",
            "matter_type": "other",
            "status": "draft",
            "due_date": "2026-12-01",
        },
    ]
    sigs = eng.detect_upcoming_legal_deadlines(matters, today=today, within_days=14)
    by_id = {s["related_id"]: s for s in sigs}
    assert set(by_id) == {"m1", "m2"}
    assert by_id["m1"]["type"] == "upcoming_legal_deadline"
    assert by_id["m1"]["severity"] == "low"
    assert "Compliance renewal for State license" in by_id["m1"]["summary"]
    assert "due in 5 days" in by_id["m1"]["summary"]
    assert by_id["m2"]["type"] == "overdue_legal_deadline"
    assert "Contract renewal for Vendor MSA" in by_id["m2"]["summary"]
    blob = " ".join(s["detail"].lower() for s in sigs)
    for banned in ("should", "must", "recommend", "advise", "consider"):
        assert banned not in blob
    assert "upcoming_legal_deadline" in eng.DELEGATE_SIGNAL_TYPES
    assert "overdue_legal_deadline" in eng.DECISION_SIGNAL_TYPES


@pytest.mark.asyncio
async def test_legal_due_date_on_calendar():
    legal = MatterStore([
        {
            "id": "mat_due",
            "workspace_id": "ws_legal_due",
            "department_id": "dept_legal",
            "title": "Permit renewal",
            "due_date": "2026-09-20",
            "status": "draft",
        },
        {
            "id": "mat_filed",
            "workspace_id": "ws_legal_due",
            "department_id": "dept_legal",
            "title": "Filed matter",
            "due_date": "2026-09-20",
            "status": "filed",
        },
    ])
    departments = MatterStore([dict(LEGAL_DEPT)])
    mock_db = MagicMock()
    mock_db.legal_matters = legal
    mock_db.production_work_orders = MatterStore()
    mock_db.procurement_requests = MatterStore()
    mock_db.departments = departments

    with patch.object(server, "db", mock_db):
        rows = await server._department_calendar_upcoming("ws_legal_due")
    ids = {r["id"] for r in rows}
    assert "mat_due" in ids
    assert "mat_filed" not in ids
    hit = next(r for r in rows if r["id"] == "mat_due")
    assert hit["type"] == "Legal"
    assert hit["title"] == "Permit renewal"
    assert hit["source_type"] == "legal_matter"


def test_calendar_registry_includes_legal():
    legal = next(s for s in server.CALENDAR_DATE_SOURCES if s["collection"] == "legal_matters")
    assert legal["date_field"] == "due_date"
    assert legal["title_field"] == "title"
    assert legal["type_label"] == "Legal"
    assert "filed" not in legal["open_statuses"]
    assert legal["open_statuses"] == frozenset({
        "draft", "internal_review", "counterparty_review", "signed",
    })
