"""Document library + download audit logging."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_document_library")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


REPORTS_ONLY = {
    "user_id": "u_reports",
    "email": "reports@acme.com",
    "name": "Reports User",
    "workspace_id": "ws_lib",
    "role": "member",
    "pack": "member",
}

OWNER = {
    "user_id": "u_owner",
    "email": "owner@acme.com",
    "name": "Owner",
    "workspace_id": "ws_lib",
    "role": "owner",
    "pack": "owner",
}


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_a, **_k):
        return self

    async def to_list(self, _n):
        return list(self._rows)


@pytest.fixture
def library_client():
    async def as_reports():
        return REPORTS_ONLY

    mock_db = MagicMock()
    mock_db.documents = MagicMock()
    mock_db.documents.find = MagicMock(return_value=_Cursor([
        {
            "id": "doc_fin_1",
            "filename": "bill.pdf",
            "content_type": "application/pdf",
            "uploaded_at": "2026-09-01T00:00:00+00:00",
            "uploaded_by": "u_owner",
            "status": "extracted",
            "storage_key": "secret/fin.pdf",
        },
    ]))
    mock_db.report_documents = MagicMock()
    mock_db.report_documents.find = MagicMock(return_value=_Cursor([
        {
            "id": "rdoc_1",
            "filename": "ops.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "uploaded_at": "2026-09-02T00:00:00+00:00",
            "uploaded_by": "u_reports",
            "report_date": "2026-09-02",
            "status": "summarized",
            "storage_key": "secret/ops.xlsx",
        },
    ]))
    mock_db.report_documents.find_one = AsyncMock(return_value={
        "id": "rdoc_1",
        "workspace_id": "ws_lib",
        "filename": "ops.xlsx",
        "storage_key": "secret/ops.xlsx",
        "content_type": "application/pdf",
    })
    mock_db.legal_matters = MagicMock()
    mock_db.legal_matters.find = MagicMock(return_value=_Cursor([
        {
            "id": "mat_1",
            "department_id": "dept_legal",
            "title": "Secret NDA",
            "assigned_to": "u_owner",
            "document_ref": {
                "document_id": "ldoc_1",
                "storage_key": "secret/nda.pdf",
                "filename": "nda.pdf",
                "content_type": "application/pdf",
                "uploaded_by": "u_owner",
                "uploaded_at": "2026-09-03T00:00:00+00:00",
            },
        },
    ]))
    mock_db.departments = MagicMock()
    mock_db.departments.find_one = AsyncMock(return_value=None)
    mock_db.activities = MagicMock()
    mock_db.activities.insert_one = AsyncMock()
    mock_db.memberships = MagicMock()
    mock_db.memberships.find_one = AsyncMock(return_value={
        "user_id": "u_reports",
        "workspace_id": "ws_lib",
        "status": "active",
        "pack": "member",
        "section_grants": {"reports": True},
    })
    mock_db.workspaces = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(return_value={
        "workspace_id": "ws_lib",
        "plan": "growth",
        "section_access": {},
    })

    async def section_write(principal, section_id, pack_perm, **_kwargs):
        if principal["user_id"] == "u_owner":
            return True
        return section_id == "reports" and pack_perm == "reports:write"

    server.app.dependency_overrides[server.get_principal] = as_reports
    with (
        patch.object(server, "db", mock_db),
        patch.object(server, "can_section_write", side_effect=section_write),
        patch.object(server, "_membership_for", new=AsyncMock(return_value={
            "user_id": "u_reports", "workspace_id": "ws_lib", "pack": "member",
            "section_grants": {},
        })),
        patch.object(server, "get_ws", new=AsyncMock(return_value={
            "workspace_id": "ws_lib", "section_access": {},
        })),
        patch.object(server, "log_activity", new_callable=AsyncMock) as log,
    ):
        client = TestClient(server.app)
        yield client, mock_db, log
    server.app.dependency_overrides.clear()


def test_library_reports_only_excludes_financial_and_legal(library_client):
    client, mock_db, log = library_client
    r = client.get("/api/documents/library")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    docs = body["documents"]
    assert len(docs) == 1
    assert docs[0]["context"] == "reports"
    assert docs[0]["id"] == "rdoc_1"
    assert docs[0]["open_path"] == "/reports/documents/rdoc_1"
    assert "presigned_url" not in docs[0]
    assert "storage_key" not in docs[0]
    # Financial and legal collections must not leak into the response.
    contexts = {d["context"] for d in docs}
    assert "financial" not in contexts
    assert "legal" not in contexts
    log.assert_awaited()
    assert log.await_args.args[2] == "document.library.view"


def test_library_owner_sees_all_contexts_without_presigned_urls():
    async def as_owner():
        return OWNER

    mock_db = MagicMock()
    mock_db.documents.find = MagicMock(return_value=_Cursor([
        {"id": "doc_1", "filename": "a.pdf", "uploaded_at": "2026-09-01", "uploaded_by": "u"},
    ]))
    mock_db.report_documents.find = MagicMock(return_value=_Cursor([
        {"id": "rdoc_1", "filename": "b.pdf", "uploaded_at": "2026-09-02", "uploaded_by": "u"},
    ]))
    mock_db.legal_matters.find = MagicMock(return_value=_Cursor([
        {
            "id": "mat_1",
            "title": "NDA",
            "assigned_to": "u_owner",
            "document_ref": {
                "document_id": "ldoc_1",
                "filename": "nda.pdf",
                "uploaded_at": "2026-09-03",
                "uploaded_by": "u_owner",
            },
        },
    ]))
    mock_db.departments.find_one = AsyncMock(return_value={
        "department_id": "dept_legal",
        "workspace_id": "ws_lib",
        "type": "legal",
        "enabled": True,
    })

    server.app.dependency_overrides[server.get_principal] = as_owner
    with (
        patch.object(server, "db", mock_db),
        patch.object(server, "can_section_write", new=AsyncMock(return_value=True)),
        patch.object(server, "_membership_for", new=AsyncMock(return_value={"pack": "owner"})),
        patch.object(server, "get_ws", new=AsyncMock(return_value={"workspace_id": "ws_lib"})),
        patch.object(server.dept_access, "can_access_department", new=AsyncMock(return_value=True)),
        patch.object(server.dept_access, "get_department_membership", new=AsyncMock(return_value={"role": "lead"})),
        patch.object(server, "log_activity", new_callable=AsyncMock),
    ):
        client = TestClient(server.app)
        r = client.get("/api/documents/library")
    server.app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    contexts = {d["context"] for d in body["documents"]}
    assert contexts == {"financial", "reports", "legal"}
    for d in body["documents"]:
        assert "presigned_url" not in d
        assert "storage_key" not in d
        assert d.get("open_path", "").startswith("/")


def test_financial_document_get_logs_download():
    async def as_owner():
        return OWNER

    doc = {
        "id": "doc_1",
        "workspace_id": "ws_lib",
        "storage_key": "k",
        "filename": "bill.pdf",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=doc)

    server.app.dependency_overrides[server.get_principal] = as_owner
    with (
        patch.object(server, "db", mock_db),
        patch.object(server, "can_section_write", new=AsyncMock(return_value=True)),
        patch.object(server.doc_storage, "get_presigned_url", return_value="https://signed.example/x"),
        patch.object(server, "log_activity", new_callable=AsyncMock) as log,
    ):
        client = TestClient(server.app)
        r = client.get("/api/documents/doc_1")
    server.app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["presigned_url"] == "https://signed.example/x"
    assert "storage_key" not in body
    assert log.await_args.args[2] == "document.download"
    assert log.await_args.args[0]["user_id"] == "u_owner"


def test_report_document_get_logs_download():
    async def as_owner():
        return OWNER

    doc = {
        "id": "rdoc_1",
        "workspace_id": "ws_lib",
        "storage_key": "k",
        "filename": "ops.pdf",
    }
    mock_db = MagicMock()
    mock_db.report_documents.find_one = AsyncMock(return_value=doc)

    server.app.dependency_overrides[server.get_principal] = as_owner
    with (
        patch.object(server, "db", mock_db),
        patch.object(server, "can_section_write", new=AsyncMock(return_value=True)),
        patch.object(server.doc_storage, "r2_configured", return_value=True),
        patch.object(server.doc_storage, "get_presigned_url", return_value="https://signed.example/r"),
        patch.object(server, "log_activity", new_callable=AsyncMock) as log,
    ):
        client = TestClient(server.app)
        r = client.get("/api/reports/documents/rdoc_1")
    server.app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["presigned_url"].startswith("https://")
    assert "storage_key" not in body
    assert log.await_args.args[2] == "document.download"
