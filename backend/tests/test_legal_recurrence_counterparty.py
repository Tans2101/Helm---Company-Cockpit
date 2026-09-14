"""Legal compliance recurrence + counterparty tracking."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_legal_recurrence_cp")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
import departments_catalog as catalog  # noqa: E402
from mongo_mocks import attach_users_in_find  # noqa: E402


CEO = {
    "user_id": "u_ceo",
    "email": "ceo@acme.com",
    "name": "CEO",
    "workspace_id": "ws_legal_r",
    "role": "owner",
    "pack": "owner",
}

LEGAL_DEPT = {
    "department_id": "dept_legal",
    "workspace_id": "ws_legal_r",
    "type": catalog.TYPE_LEGAL,
    "name": "Legal",
    "enabled": True,
}


def _match(doc, query):
    for k, v in (query or {}).items():
        if isinstance(v, dict):
            continue
        if doc.get(k) != v:
            return False
    return True


class MatterStore:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                return {k: v for k, v in r.items() if k != "_id"}
        return None

    def find(self, query, projection=None):
        matched = []
        for r in self.rows:
            ok = True
            for k, v in (query or {}).items():
                if isinstance(v, dict):
                    continue
                if r.get(k) != v:
                    ok = False
                    break
            if ok:
                matched.append(dict(r))

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
            if all(r.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
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


def test_advance_legal_due_date_helper():
    assert server._advance_legal_due_date("2026-09-21", "annual") == "2027-09-21"
    assert server._advance_legal_due_date("2026-01-31", "monthly") == "2026-02-28"
    assert server._advance_legal_due_date("2026-01-31", "quarterly") == "2026-04-30"
    assert server._advance_legal_due_date("", "annual") == ""


def test_filing_recurring_compliance_spawns_next_cycle(legal_api):
    client, store = legal_api
    r = client.post("/api/legal/matters", json={
        "title": "Business license",
        "matter_type": "compliance",
        "due_date": "2026-09-21",
        "recurrence": "annual",
        "counterparty": "State of CA",
    })
    assert r.status_code == 200, r.text
    matter = r.json()["matter"]
    assert matter["recurrence"] == "annual"
    assert len(store.rows) == 1

    r2 = client.patch(f"/api/legal/matters/{matter['id']}", json={"status": "filed"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["matter"]["status"] == "filed"
    renewal = body["renewal_matter"]
    assert renewal is not None
    assert renewal["status"] == "draft"
    assert renewal["matter_type"] == "compliance"
    assert renewal["recurrence"] == "annual"
    assert renewal["due_date"] == "2027-09-21"
    assert renewal["renewed_from_matter_id"] == matter["id"]
    assert renewal["title"] == "Business license"
    assert renewal["counterparty"] == "State of CA"
    assert body["matter"]["renewed_to_matter_id"] == renewal["id"]
    assert len(store.rows) == 2

    # Re-file after un-file does not duplicate
    client.patch(f"/api/legal/matters/{matter['id']}", json={"status": "signed"})
    r3 = client.patch(f"/api/legal/matters/{matter['id']}", json={"status": "filed"})
    assert r3.status_code == 200, r3.text
    assert len(store.rows) == 2
    assert r3.json()["renewal_matter"]["id"] == renewal["id"]


def test_filing_non_recurring_does_not_spawn(legal_api):
    client, store = legal_api
    r = client.post("/api/legal/matters", json={
        "title": "One-off filing",
        "matter_type": "compliance",
        "due_date": "2026-09-21",
    })
    mid = r.json()["matter"]["id"]
    r2 = client.patch(f"/api/legal/matters/{mid}", json={"status": "filed"})
    assert r2.status_code == 200
    assert r2.json().get("renewal_matter") is None
    assert len(store.rows) == 1


def test_recurrence_ignored_on_contract(legal_api):
    client, store = legal_api
    r = client.post("/api/legal/matters", json={
        "title": "MSA",
        "matter_type": "contract",
        "recurrence": "annual",
    })
    assert r.status_code == 200, r.text
    assert r.json()["matter"]["recurrence"] is None


def test_counterparty_filter_and_suggestions(legal_api):
    client, store = legal_api
    for title, cp in [
        ("NDA A", "Acme Corp"),
        ("MSA A", "Acme Corp"),
        ("NDA B", "Beta LLC"),
    ]:
        r = client.post("/api/legal/matters", json={
            "title": title,
            "matter_type": "contract",
            "counterparty": cp,
        })
        assert r.status_code == 200, r.text

    listed = client.get("/api/legal/matters", params={"counterparty": "Acme Corp"})
    assert listed.status_code == 200
    titles = {m["title"] for m in listed.json()["matters"]}
    assert titles == {"NDA A", "MSA A"}

    sug = client.get("/api/legal/counterparty-suggestions", params={"q": "acme"})
    assert sug.status_code == 200, sug.text
    suggestions = sug.json()["suggestions"]
    assert suggestions
    assert suggestions[0]["counterparty"] == "Acme Corp"
    assert suggestions[0]["matter_count"] == 2
    assert "last_matter_date" in suggestions[0]
