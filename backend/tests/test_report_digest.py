"""Report digest: spreadsheet text conversion + upload/summarize API."""
import io
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_report_digest")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import report_text  # noqa: E402
import server  # noqa: E402
from llm import _validate_report_summary  # noqa: E402

MOCK_PRINCIPAL = {
    "user_id": "test-user-reports",
    "email": "reports@example.com",
    "name": "Report Tester",
    "workspace_id": "ws_report_test",
    "role": "owner",
    "pack": "owner",
}

PDF_BYTES = b"%PDF-1.4 minimal test content"


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_csv_to_text_includes_figures_and_caps_rows():
    lines = ["commodity,price"] + [f"wheat,{i}" for i in range(500)]
    data = "\n".join(lines).encode("utf-8")
    text, truncated = report_text.spreadsheet_bytes_to_text(data, "text/csv", "prices.csv")
    assert "wheat" in text
    assert truncated is True
    assert "Truncated" in text


def test_xlsx_to_text_reads_cells():
    data = _xlsx_bytes([["Item", "Price"], ["Copper", "4.52"], ["Zinc", "1.10"]])
    text, truncated = report_text.spreadsheet_bytes_to_text(
        data,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "metals.xlsx",
    )
    assert "Copper" in text
    assert "4.52" in text
    assert truncated is False


def test_validate_report_summary_grounding_shape():
    out = _validate_report_summary({
        "summary": "Copper closed at 4.52.",
        "key_figures": [{"label": "Copper", "value": "4.52"}, {"label": "", "value": "x"}],
        "unclear": False,
    })
    assert out["summary"].startswith("Copper")
    assert out["key_figures"] == [{"label": "Copper", "value": "4.52"}]
    assert out["unclear"] is False


def test_validate_unclear_empty_summary():
    out = _validate_report_summary({"summary": "", "key_figures": [], "unclear": False})
    assert out["unclear"] is True
    assert "could not be summarized" in out["summary"].lower()


@pytest.fixture
def client():
    async def mock_principal():
        return MOCK_PRINCIPAL

    server.app.dependency_overrides[server.get_principal] = mock_principal
    mock_db = MagicMock()
    mock_db.report_documents = MagicMock()
    mock_db.report_documents.insert_one = AsyncMock(return_value=None)
    mock_db.report_documents.find_one = AsyncMock(return_value=None)
    mock_db.report_documents.update_one = AsyncMock(return_value=None)
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    mock_db.report_documents.find.return_value = cursor
    mock_db.documents = MagicMock()
    mock_db.documents.insert_one = AsyncMock(return_value=None)
    mock_db.activities = MagicMock()
    mock_db.activities.insert_one = AsyncMock(return_value=None)
    mock_db.document_rate_events = MagicMock()
    mock_db.document_rate_events.count_documents = AsyncMock(return_value=0)
    mock_db.document_rate_events.insert_one = AsyncMock(return_value=None)
    mock_db.document_rate_buckets = MagicMock()
    mock_db.document_rate_buckets.find_one_and_update = AsyncMock(
        return_value={"_id": "ws_report_test:upload", "count": 1},
    )
    mock_db.workspaces = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(return_value={
        "workspace_id": "ws_report_test",
        "plan": "business",
        "subscription_status": "active",
    })
    mock_db.memberships = MagicMock()
    mock_db.memberships.find_one = AsyncMock(return_value={
        "user_id": MOCK_PRINCIPAL["user_id"], "workspace_id": "ws_report_test",
        "status": "active", "pack": "owner", "role": "owner", "section_grants": {},
    })

    with patch.object(server, "db", mock_db), patch.object(
        server.doc_storage, "r2_configured", return_value=True
    ), patch.object(
        server.doc_storage, "upload_document", return_value="ws_report_test/report.xlsx"
    ), patch.object(
        server, "log_activity", new_callable=AsyncMock, return_value=None
    ), patch.object(
        server, "can_section_write", new_callable=AsyncMock, return_value=True
    ), patch.object(
        server, "get_ws", new_callable=AsyncMock, return_value={
            "workspace_id": "ws_report_test", "plan": "business", "subscription_status": "active",
            "billing_period_start": "2026-01-01T00:00:00+00:00",
        }
    ), patch.object(server, "BILLING_ENFORCED", False), patch.object(
        server.plan_usage, "increment_period_extract", new_callable=AsyncMock, return_value=None
    ), patch.object(
        server.plan_usage, "increment_lifetime_extract", new_callable=AsyncMock, return_value=None
    ), patch.object(
        server, "_product_event", new_callable=AsyncMock, return_value=None
    ):
        yield TestClient(server.app)
    server.app.dependency_overrides.clear()


def test_report_upload_accepts_xlsx(client):
    data = _xlsx_bytes([["A", "B"], [1, 2]])
    r = client.post(
        "/api/reports/documents/upload",
        files={"file": (
            "prices.xlsx",
            io.BytesIO(data),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "uploaded"
    assert body["document_id"].startswith("rdoc_")


def test_report_upload_accepts_csv(client):
    r = client.post(
        "/api/reports/documents/upload",
        files={"file": ("prices.csv", io.BytesIO(b"item,price\nwheat,210\n"), "text/csv")},
    )
    assert r.status_code == 200, r.text


def test_bills_upload_still_rejects_xlsx(client):
    data = _xlsx_bytes([["A"], [1]])
    r = client.post(
        "/api/documents/upload",
        files={"file": (
            "prices.xlsx",
            io.BytesIO(data),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )},
    )
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"].lower()


def test_report_summarize_xlsx(client):
    data = _xlsx_bytes([["Metal", "Price"], ["Copper", "4.52"]])
    doc_id = "rdoc_test123"
    server.db.report_documents.find_one = AsyncMock(return_value={
        "id": doc_id,
        "workspace_id": MOCK_PRINCIPAL["workspace_id"],
        "storage_key": "ws_report_test/key.xlsx",
        "filename": "metals.xlsx",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "status": "uploaded",
        "report_date": "2026-09-15",
    })
    with patch.object(server.doc_storage, "get_document_bytes", return_value=data), patch.object(
        server.helm_llm, "anthropic_configured", return_value=True
    ), patch.object(
        server.helm_llm, "summarize_report_document", new_callable=AsyncMock,
        return_value={
            "summary": "Copper is listed at 4.52.",
            "key_figures": [{"label": "Copper", "value": "4.52"}],
            "unclear": False,
        },
    ) as summarize:
        r = client.post(f"/api/reports/documents/{doc_id}/summarize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"] == "Copper is listed at 4.52."
    assert body["key_figures"][0]["value"] == "4.52"
    summarize.assert_awaited_once()
    # First arg to summarize should be converted text, not raw bytes
    args = summarize.await_args.args
    assert isinstance(args[0], str)
    assert "Copper" in args[0]


def test_digest_empty_day(client):
    r = client.get("/api/reports/digest", params={"date": "2026-09-15"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == "2026-09-15"
    assert body["reports"] == []
    assert body["combined_digest"] == ""


def test_digest_combines_summaries(client):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[
        {
            "id": "rdoc_1",
            "filename": "copper.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "uploaded_at": "2026-09-15T10:00:00+00:00",
            "status": "summarized",
            "summary": "Copper closed at 4.52.",
            "key_figures": [{"label": "Copper", "value": "4.52"}],
            "unclear": False,
            "summarized_at": "2026-09-15T10:01:00+00:00",
        },
        {
            "id": "rdoc_2",
            "filename": "zinc.csv",
            "content_type": "text/csv",
            "uploaded_at": "2026-09-15T11:00:00+00:00",
            "status": "summarized",
            "summary": "Zinc closed at 1.10.",
            "key_figures": [{"label": "Zinc", "value": "1.10"}],
            "unclear": False,
            "summarized_at": "2026-09-15T11:01:00+00:00",
        },
    ])
    server.db.report_documents.find.return_value = cursor
    with patch.object(
        server.helm_llm, "combine_daily_report_digest", new_callable=AsyncMock,
        return_value="Copper closed at 4.52 and zinc at 1.10.",
    ) as combine:
        r = client.get("/api/reports/digest", params={"date": "2026-09-15"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["reports"]) == 2
    assert "4.52" in body["combined_digest"]
    combine.assert_awaited_once()
