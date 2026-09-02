"""Document upload + AI extraction for financial entries."""
import io
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_documents")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402
import routes.financials  # noqa: E402
import storage as doc_storage_mod  # noqa: E402
import llm as helm_llm_mod  # noqa: E402

MOCK_PRINCIPAL = {
    "user_id": "test-user-docs",
    "email": "docs@example.com",
    "name": "Doc Tester",
    "workspace_id": "ws_doc_test",
    "role": "owner",
    "pack": "owner",
}

PDF_BYTES = b"%PDF-1.4 minimal test content"
OVERSIZED = b"x" * (15 * 1024 * 1024 + 1)


@pytest.fixture
def client():
    async def mock_principal():
        return MOCK_PRINCIPAL

    server.app.dependency_overrides[server.get_principal] = mock_principal
    mock_db = MagicMock()
    mock_db.documents = MagicMock()
    mock_db.documents.insert_one = AsyncMock(return_value=None)
    mock_db.documents.find_one = AsyncMock(return_value=None)
    mock_db.documents.update_one = AsyncMock(return_value=None)
    mock_db.activities = MagicMock()
    mock_db.activities.insert_one = AsyncMock(return_value=None)

    with patch("routes.financials.db", mock_db), patch("helpers.db", mock_db), patch("db.db", mock_db), patch("routes.financials.doc_storage", doc_storage_mod), patch.object(doc_storage_mod, "r2_configured", return_value=True), patch.object(
        doc_storage_mod, "upload_document", return_value="ws_doc_test/test-key.pdf"
    ), patch("helpers.log_activity", new_callable=AsyncMock, return_value=None):
        yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def test_upload_valid_pdf(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("invoice.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "uploaded"
    assert body["document_id"].startswith("doc_")


def test_upload_oversized_rejected(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("huge.pdf", io.BytesIO(OVERSIZED), "application/pdf")},
    )
    assert r.status_code == 400
    assert "15MB" in r.json()["detail"]


def test_upload_wrong_content_type_rejected(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"].lower()


def test_extract_not_financial_returns_error_json(client):
    doc_id = "doc_test123"
    routes.financials.db.documents.find_one = AsyncMock(return_value={
        "id": doc_id,
        "workspace_id": MOCK_PRINCIPAL["workspace_id"],
        "storage_key": "ws_doc_test/key.pdf",
        "filename": "resume.pdf",
        "content_type": "application/pdf",
        "status": "uploaded",
    })

    with patch.object(doc_storage_mod, "get_document_bytes", return_value=PDF_BYTES), patch.object(
        helm_llm_mod, "anthropic_configured", return_value=True
    ), patch.object(
        helm_llm_mod, "extract_financial_document", new_callable=AsyncMock, return_value={"error": "not_financial"}
    ):
        r = client.post(f"/api/documents/{doc_id}/extract")

    assert r.status_code == 200
    assert r.json() == {"error": "not_financial"}
