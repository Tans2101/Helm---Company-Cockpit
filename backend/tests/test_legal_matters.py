"""Legal matter queue API tests."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_legal_matters")

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

OTHER = {
    "user_id": "u_other",
    "email": "other@acme.com",
    "name": "Other",
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

LEGAL_DEPT = {
    "department_id": "dept_legal",
    "workspace_id": "ws_test",
    "type": "legal",
    "name": "Legal",
    "enabled": True,
}


class MatterStore:
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
                    items.sort(key=lambda x: x.get(field) or "", reverse=direction == -1)
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
def legal_api():
    store = MatterStore()
    depts = MagicMock()
    depts.find_one = AsyncMock(return_value=dict(LEGAL_DEPT))
    members = MagicMock()

    async def member_find_one(query, projection=None):
        uid = query.get("user_id")
        roles = {
            "u_mem": "member",
            "u_other": "member",
            "u_lead": "lead",
        }
        if uid in roles:
            return {"department_id": "dept_legal", "user_id": uid, "role": roles[uid]}
        return None

    members.find_one = AsyncMock(side_effect=member_find_one)
    users = MagicMock()
    users.find_one = AsyncMock(return_value={"name": "Mem", "email": "mem@acme.com"})

    mock_db = MagicMock()
    mock_db.departments = depts
    mock_db.department_members = members
    mock_db.legal_matters = store
    mock_db.users = users

    async def as_ceo():
        return CEO

    async def as_member():
        return MEMBER

    async def as_other():
        return OTHER

    async def as_lead():
        return LEAD

    async def as_outsider():
        return OUTSIDER

    server.app.dependency_overrides[server.get_principal] = as_member
    with patch.object(server, "db", mock_db), \
         patch.object(server, "BILLING_ENFORCED", False):
        client = TestClient(server.app)
        yield client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts
    server.app.dependency_overrides.clear()


def test_legal_not_placeholder():
    assert catalog.TYPE_LEGAL not in catalog.PLACEHOLDER_SHELL_TYPES


def test_outsider_403(legal_api):
    client, store, *rest = legal_api
    as_outsider = rest[4]
    server.app.dependency_overrides[server.get_principal] = as_outsider
    assert client.get("/api/legal/matters").status_code == 403
    assert client.post("/api/legal/matters", json={"title": "NDA"}).status_code == 403


def test_create_sets_created_by(legal_api):
    client, store, *_ = legal_api
    r = client.post("/api/legal/matters", json={
        "title": "NDA — Acme",
        "matter_type": "contract",
        "created_by": "u_hacker",
    })
    assert r.status_code == 200, r.text
    body = r.json()["matter"]
    assert body["created_by"] == "u_mem"
    assert body["assigned_to"] == "u_mem"
    assert body["status"] == "draft"
    assert store.rows[0]["created_by"] == "u_mem"


def test_assignee_can_advance_to_internal_review_not_beyond(legal_api):
    client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts = legal_api
    client.post("/api/legal/matters", json={"title": "MSA"})
    mid = store.rows[0]["id"]
    r = client.patch(f"/api/legal/matters/{mid}", json={"status": "internal_review", "notes": "ready"})
    assert r.status_code == 200, r.text
    assert store.rows[0]["status"] == "internal_review"
    assert store.rows[0]["notes"] == "ready"

    r2 = client.patch(f"/api/legal/matters/{mid}", json={"status": "counterparty_review"})
    assert r2.status_code == 403
    assert store.rows[0]["status"] == "internal_review"

    r3 = client.patch(f"/api/legal/matters/{mid}", json={"status": "signed"})
    assert r3.status_code == 403


def test_member_cannot_reassign(legal_api):
    client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts = legal_api
    client.post("/api/legal/matters", json={"title": "MSA"})
    mid = store.rows[0]["id"]
    r = client.patch(f"/api/legal/matters/{mid}", json={"assigned_to": "u_other"})
    assert r.status_code == 403
    assert store.rows[0]["assigned_to"] == "u_mem"


def test_lead_can_reassign_and_advance(legal_api):
    client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts = legal_api
    client.post("/api/legal/matters", json={"title": "MSA"})
    mid = store.rows[0]["id"]
    server.app.dependency_overrides[server.get_principal] = as_lead
    r = client.patch(f"/api/legal/matters/{mid}", json={
        "assigned_to": "u_other",
        "status": "counterparty_review",
    })
    assert r.status_code == 200, r.text
    assert store.rows[0]["assigned_to"] == "u_other"
    assert store.rows[0]["status"] == "counterparty_review"


def test_non_assignee_cannot_update(legal_api):
    client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts = legal_api
    client.post("/api/legal/matters", json={"title": "MSA"})
    mid = store.rows[0]["id"]
    server.app.dependency_overrides[server.get_principal] = as_other
    r = client.patch(f"/api/legal/matters/{mid}", json={"notes": "nope"})
    assert r.status_code == 403


def test_independent_matters(legal_api):
    client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts = legal_api
    client.post("/api/legal/matters", json={"title": "A"})
    client.post("/api/legal/matters", json={"title": "B"})
    a, b = store.rows[0]["id"], store.rows[1]["id"]
    client.patch(f"/api/legal/matters/{a}", json={"status": "internal_review"})
    assert store.rows[0]["status"] == "internal_review"
    assert store.rows[1]["status"] == "draft"


def test_document_upload_and_replace(legal_api):
    client, store, *_ = legal_api
    client.post("/api/legal/matters", json={"title": "NDA"})
    mid = store.rows[0]["id"]
    with patch.object(server.doc_storage, "r2_configured", return_value=True), \
         patch.object(server.doc_storage, "upload_document", return_value="ws/key1.pdf") as up, \
         patch.object(server.doc_storage, "delete_document", return_value=None) as delete:
        r = client.post(
            f"/api/legal/matters/{mid}/document",
            files={"file": ("nda.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert r.status_code == 200, r.text
        assert store.rows[0]["document_ref"]["storage_key"] == "ws/key1.pdf"
        assert r.json()["matter"]["has_document"] is True
        up.assert_called()

        with patch.object(server.doc_storage, "upload_document", return_value="ws/key2.pdf"):
            r2 = client.post(
                f"/api/legal/matters/{mid}/document",
                files={"file": ("nda2.pdf", b"%PDF-1.5", "application/pdf")},
            )
            assert r2.status_code == 200
            assert store.rows[0]["document_ref"]["storage_key"] == "ws/key2.pdf"
            delete.assert_called_with("ws/key1.pdf")


def test_document_presigned(legal_api):
    client, store, *_ = legal_api
    client.post("/api/legal/matters", json={"title": "NDA"})
    mid = store.rows[0]["id"]
    store.rows[0]["document_ref"] = {
        "document_id": "ldoc_1",
        "storage_key": "ws/key.pdf",
        "filename": "nda.pdf",
        "content_type": "application/pdf",
    }
    with patch.object(server.doc_storage, "r2_configured", return_value=True), \
         patch.object(server.doc_storage, "get_presigned_url", return_value="https://example.com/doc"):
        r = client.get(f"/api/legal/matters/{mid}/document")
        assert r.status_code == 200
        assert r.json()["presigned_url"] == "https://example.com/doc"


def test_delete_lead_only_removes_doc(legal_api):
    client, store, as_ceo, as_member, as_other, as_lead, as_outsider, depts = legal_api
    client.post("/api/legal/matters", json={"title": "NDA"})
    mid = store.rows[0]["id"]
    store.rows[0]["document_ref"] = {"storage_key": "ws/gone.pdf", "filename": "x.pdf"}
    r = client.delete(f"/api/legal/matters/{mid}")
    assert r.status_code == 403

    server.app.dependency_overrides[server.get_principal] = as_lead
    with patch.object(server.doc_storage, "r2_configured", return_value=True), \
         patch.object(server.doc_storage, "delete_document") as delete:
        r2 = client.delete(f"/api/legal/matters/{mid}")
        assert r2.status_code == 200
        assert store.rows == []
        delete.assert_called_with("ws/gone.pdf")


def test_list_status_filter(legal_api):
    client, store, *_ = legal_api
    client.post("/api/legal/matters", json={"title": "A"})
    client.post("/api/legal/matters", json={"title": "B"})
    store.rows[0]["status"] = "filed"
    r = client.get("/api/legal/matters?status=filed")
    assert r.status_code == 200
    assert len(r.json()["matters"]) == 1
    assert r.json()["matters"][0]["title"] == "A"
