"""Department framework foundation tests."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_departments_framework")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
import departments_catalog as catalog  # noqa: E402
import department_access as access  # noqa: E402

CEO = {
    "user_id": "u_ceo",
    "email": "ceo@acme.com",
    "name": "CEO",
    "workspace_id": "ws_test",
    "role": "owner",
    "pack": "owner",
}

MEMBER = {
    "user_id": "u_member",
    "email": "alex@acme.com",
    "name": "Alex",
    "workspace_id": "ws_test",
    "role": "member",
    "pack": "member",
}


def test_catalog_has_seven_types():
    assert len(catalog.DEPARTMENT_CATALOG) == 7
    assert "production" in catalog.VALID_DEPARTMENT_TYPES
    assert "accounting_finance" in catalog.VALID_DEPARTMENT_TYPES


def test_is_workspace_ceo():
    assert access.is_workspace_ceo(CEO) is True
    assert access.is_workspace_ceo(MEMBER) is False


class FakeDepartments:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items() if k != "enabled"):
                if "enabled" in query and r.get("enabled") != query["enabled"]:
                    continue
                return {k: v for k, v in r.items() if k != "_id"}
            # partial match for department_id + workspace_id
            ok = True
            for k, v in query.items():
                if r.get(k) != v:
                    ok = False
                    break
            if ok:
                return dict(r)
        return None

    def find(self, query, projection=None):
        matched = []
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                matched.append(dict(r))
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=matched)
        return cursor

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def delete_one(self, query):
        before = len(self.rows)
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]
        return MagicMock(deleted_count=before - len(self.rows))

    async def update_one(self, query, update):
        pass


class FakeDeptMembers:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if all(r.get(k) == v for k, v in query.items())]
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=matched)
        return cursor

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def delete_one(self, query):
        before = len(self.rows)
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]
        return MagicMock(deleted_count=before - len(self.rows))

    async def delete_many(self, query):
        before = len(self.rows)
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]
        return MagicMock(deleted_count=before - len(self.rows))

    async def update_one(self, query, update):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                r.update(update.get("$set") or {})
                return


@pytest.fixture
def dept_api():
    depts = FakeDepartments()
    members = FakeDeptMembers()
    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.memberships.find_one = AsyncMock(return_value={
        "user_id": "u_member", "workspace_id": "ws_test", "status": "active",
    })
    mock_db.users.find_one = AsyncMock(return_value={"name": "Alex", "email": "alex@acme.com"})
    # production_stages for dependent-data guard
    mock_db.production_stages = MagicMock()
    mock_db.production_stages.find_one = AsyncMock(return_value=None)
    # HR enable seeds default onboarding template
    hr_templates = []

    async def hr_find_one(query, projection=None):
        for r in hr_templates:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None

    async def hr_insert_one(doc):
        hr_templates.append(dict(doc))

    mock_db.hr_onboarding_template = MagicMock()
    mock_db.hr_onboarding_template.find_one = AsyncMock(side_effect=hr_find_one)
    mock_db.hr_onboarding_template.insert_one = AsyncMock(side_effect=hr_insert_one)
    mock_db.hr_onboarding_instances = MagicMock()
    mock_db.hr_onboarding_instances.find_one = AsyncMock(return_value=None)

    async def as_ceo():
        return CEO

    async def as_member():
        return MEMBER

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db), \
         patch.object(access, "db", mock_db, create=True), \
         patch.object(server, "BILLING_ENFORCED", False):
        # department_access uses db passed as arg, not module db
        client = TestClient(server.app)
        yield client, depts, members, mock_db, as_ceo, as_member
    server.app.dependency_overrides.clear()


def test_ceo_enable_and_list(dept_api):
    client, depts, members, mock_db, as_ceo, as_member = dept_api
    r = client.post("/api/departments", json={"type": "production"})
    assert r.status_code == 200, r.text
    assert depts.rows and depts.rows[0]["type"] == "production"
    assert depts.rows[0]["enabled"] is True

    r2 = client.post("/api/departments", json={"type": "production"})
    assert r2.status_code == 409

    r3 = client.get("/api/departments")
    assert r3.status_code == 200
    body = r3.json()
    assert body["is_ceo"] is True
    prod = next(d for d in body["departments"] if d["type"] == "production")
    assert prod["enabled"] is True
    assert prod["visible_in_nav"] is True  # CEO sees enabled even without membership


def test_member_cannot_enable(dept_api):
    client, depts, members, mock_db, as_ceo, as_member = dept_api
    server.app.dependency_overrides[server.get_principal] = as_member
    r = client.post("/api/departments", json={"type": "legal"})
    assert r.status_code == 403


def test_member_nav_visibility(dept_api):
    client, depts, members, mock_db, as_ceo, as_member = dept_api
    client.post("/api/departments", json={"type": "production"})
    client.post("/api/departments", json={"type": "legal"})
    dept_id = depts.rows[0]["department_id"]
    members.rows.append({
        "department_id": dept_id,
        "user_id": "u_member",
        "role": "member",
        "created_at": "2026-01-01",
    })

    server.app.dependency_overrides[server.get_principal] = as_member
    r = client.get("/api/departments")
    assert r.status_code == 200
    by_type = {d["type"]: d for d in r.json()["departments"]}
    assert by_type["production"]["visible_in_nav"] is True
    assert by_type["legal"]["visible_in_nav"] is False
    assert by_type["hr"]["visible_in_nav"] is False


def test_by_type_access_denied_for_non_member(dept_api):
    client, depts, members, mock_db, as_ceo, as_member = dept_api
    client.post("/api/departments", json={"type": "production"})
    server.app.dependency_overrides[server.get_principal] = as_member
    r = client.get("/api/departments/by-type/production")
    assert r.status_code == 403


def test_disable_blocked_with_dependent_data(dept_api):
    client, depts, members, mock_db, as_ceo, as_member = dept_api
    client.post("/api/departments", json={"type": "production"})
    dept_id = depts.rows[0]["department_id"]
    mock_db.production_stages.find_one = AsyncMock(return_value={"_id": "x"})
    r = client.delete(f"/api/departments/{dept_id}")
    assert r.status_code == 400
    assert "department-specific data" in r.json()["detail"]


def test_add_and_remove_member(dept_api):
    client, depts, members, mock_db, as_ceo, as_member = dept_api
    client.post("/api/departments", json={"type": "hr"})
    dept_id = depts.rows[0]["department_id"]
    r = client.post(f"/api/departments/{dept_id}/members", json={"user_id": "u_member", "role": "lead"})
    assert r.status_code == 200, r.text
    assert any(m["user_id"] == "u_member" for m in members.rows)
    r2 = client.delete(f"/api/departments/{dept_id}/members/u_member")
    assert r2.status_code == 200
    assert not members.rows
