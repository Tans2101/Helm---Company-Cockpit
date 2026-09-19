"""Department date sources on GET /calendar (extensible CALENDAR_DATE_SOURCES)."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_calendar_department_dates")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402


CEO = {
    "user_id": "u_ceo",
    "email": "ceo@acme.com",
    "name": "CEO",
    "workspace_id": "ws_cal",
    "role": "owner",
    "pack": "owner",
}


def _match(doc: dict, query: dict) -> bool:
    if not query:
        return True
    for k, v in query.items():
        if k == "$or":
            if not any(_match(doc, clause) for clause in v):
                return False
            continue
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


class DocStore:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if _match(r, query or {})]

        class C:
            async def to_list(self, n):
                return matched[:n]

            def sort(self, *a, **k):
                return self

        return C()

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if _match(r, query or {}):
                return dict(r)
        return None


@pytest.fixture
def cal_db():
    production = DocStore()
    procurement = DocStore()
    departments = DocStore([
        {
            "department_id": "dept_prod",
            "workspace_id": "ws_cal",
            "type": "production",
            "enabled": True,
        },
        {
            "department_id": "dept_proc",
            "workspace_id": "ws_cal",
            "type": "procurement",
            "enabled": True,
        },
    ])
    mock_db = MagicMock()
    mock_db.production_work_orders = production
    mock_db.procurement_requests = procurement
    mock_db.departments = departments
    return mock_db, production, procurement, departments


@pytest.mark.asyncio
async def test_department_upcoming_includes_open_dated_rows(cal_db):
    mock_db, production, procurement, _ = cal_db
    production.rows.extend([
        {
            "id": "pwo_1",
            "workspace_id": "ws_cal",
            "department_id": "dept_prod",
            "reference": "Order #245",
            "due_date": "2026-09-16",
            "status": "awaiting_materials",
        },
        {
            "id": "pwo_done",
            "workspace_id": "ws_cal",
            "department_id": "dept_prod",
            "reference": "Finished job",
            "due_date": "2026-09-16",
            "status": "completed",
        },
        {
            # Orphan from a previous department id — must not appear.
            "id": "pwo_orphan",
            "workspace_id": "ws_cal",
            "department_id": "dept_prod_old",
            "reference": "Orphan",
            "due_date": "2026-09-16",
            "status": "in_production",
        },
    ])
    procurement.rows.extend([
        {
            "id": "preq_1",
            "workspace_id": "ws_cal",
            "department_id": "dept_proc",
            "item": "Steel plate",
            "expected_delivery_date": "2026-09-17",
            "status": "ordered",
        },
        {
            "id": "preq_delivered",
            "workspace_id": "ws_cal",
            "department_id": "dept_proc",
            "item": "Old bolts",
            "expected_delivery_date": "2026-09-17",
            "status": "delivered",
        },
        {
            "id": "preq_rejected",
            "workspace_id": "ws_cal",
            "department_id": "dept_proc",
            "item": "Bad lot",
            "expected_delivery_date": "2026-09-17",
            "status": "rejected",
        },
    ])

    with patch.object(server, "db", mock_db):
        rows = await server._department_calendar_upcoming("ws_cal")

    by_id = {r["id"]: r for r in rows}
    assert "pwo_1" in by_id
    assert by_id["pwo_1"]["type"] == "Production"
    assert by_id["pwo_1"]["title"] == "Order #245"
    assert by_id["pwo_1"]["date"] == "2026-09-16"
    assert by_id["pwo_1"]["source_type"] == "production_work_order"
    assert by_id["pwo_1"]["source_id"] == "pwo_1"

    assert "preq_1" in by_id
    assert by_id["preq_1"]["type"] == "Procurement"
    assert by_id["preq_1"]["title"] == "Steel plate"
    assert by_id["preq_1"]["source_type"] == "procurement_request"

    assert "pwo_done" not in by_id
    assert "pwo_orphan" not in by_id
    assert "preq_delivered" not in by_id
    assert "preq_rejected" not in by_id


@pytest.mark.asyncio
async def test_skips_disabled_department(cal_db):
    mock_db, production, procurement, departments = cal_db
    departments.rows = [{
        "department_id": "dept_proc",
        "workspace_id": "ws_cal",
        "type": "procurement",
        "enabled": True,
    }]
    production.rows.append({
        "id": "pwo_1",
        "workspace_id": "ws_cal",
        "department_id": "dept_prod",
        "reference": "Hidden",
        "due_date": "2026-09-16",
        "status": "in_production",
    })
    procurement.rows.append({
        "id": "preq_1",
        "workspace_id": "ws_cal",
        "department_id": "dept_proc",
        "item": "Visible",
        "expected_delivery_date": "2026-09-16",
        "status": "ordered",
    })
    with patch.object(server, "db", mock_db):
        rows = await server._department_calendar_upcoming("ws_cal")
    assert {r["id"] for r in rows} == {"preq_1"}


@pytest.mark.asyncio
async def test_registry_entry_alone_surfaces_new_source(cal_db):
    """Adding a CALENDAR_DATE_SOURCES row is enough — no endpoint changes."""
    mock_db, _, _, departments = cal_db
    mock_db.legal_matters = DocStore([{
        "id": "mat_1",
        "workspace_id": "ws_cal",
        "department_id": "dept_legal",
        "title": "Contract renewal",
        "deadline": "2026-09-18",
        "status": "open",
    }])
    departments.rows.append({
        "department_id": "dept_legal",
        "workspace_id": "ws_cal",
        "type": "legal",
        "enabled": True,
    })
    extra = {
        "collection": "legal_matters",
        "date_field": "deadline",
        "title_field": "title",
        "type_label": "Legal",
        "department_type": "legal",
        "open_statuses": frozenset({"open"}),
        "source_type": "legal_matter",
    }
    with patch.object(server, "db", mock_db), \
         patch.object(server, "CALENDAR_DATE_SOURCES", list(server.CALENDAR_DATE_SOURCES) + [extra]):
        rows = await server._department_calendar_upcoming("ws_cal")
    hit = [r for r in rows if r["id"] == "mat_1"]
    assert len(hit) == 1
    assert hit[0]["type"] == "Legal"
    assert hit[0]["source_type"] == "legal_matter"


def test_deadlines_as_events_preserves_source_refs():
    events = server._deadlines_as_events([{
        "id": "pwo_1",
        "title": "Order #245",
        "date": "2026-09-16",
        "type": "Production",
        "source_type": "production_work_order",
        "source_id": "pwo_1",
    }])
    assert len(events) == 1
    assert events[0]["type"] == "Production"
    assert events[0]["source"] == "deadline"
    assert events[0]["source_type"] == "production_work_order"
    assert events[0]["source_id"] == "pwo_1"
    assert events[0]["all_day"] is True


def test_calendar_endpoint_merges_department_and_legacy_deadlines(cal_db):
    mock_db, production, procurement, _ = cal_db
    production.rows.append({
        "id": "pwo_1",
        "workspace_id": "ws_cal",
        "department_id": "dept_prod",
        "reference": "Order #245",
        "due_date": "2026-09-16",
        "status": "quality_check",
    })
    procurement.rows.append({
        "id": "preq_1",
        "workspace_id": "ws_cal",
        "department_id": "dept_proc",
        "item": "Steel plate",
        "expected_delivery_date": "2026-09-16",
        "status": "ordered",
    })
    ws = {
        "workspace_id": "ws_cal",
        "calendar": {"meetings": [], "helm_events": []},
        "decisions": [
            {"id": "dec_1", "title": "Hire ops lead", "due": "2026-09-16",
             "status": "pending", "category": "People"},
        ],
        "tasks": {
            "items": [
                {"id": "task_1", "title": "Send invoice", "due": "2026-09-16",
                 "column": "doing", "assignee_user_id": "u_ceo", "tag": "Finance"},
                {"id": "task_done", "title": "Done task", "due": "2026-09-16",
                 "column": "done", "assignee_user_id": "u_ceo", "tag": ""},
            ],
        },
        "google_tokens": None,
    }

    async def as_ceo():
        return CEO

    server.app.dependency_overrides[server.get_principal] = as_ceo
    try:
        with patch.object(server, "db", mock_db), \
             patch.object(server, "get_ws", AsyncMock(return_value=ws)), \
             patch.object(server, "_google_calendar_snapshot", AsyncMock(return_value=None)), \
             patch.object(server, "_user_google_tokens_present", AsyncMock(return_value=False)), \
             patch.object(server, "_user_google_tokens", AsyncMock(return_value=None)), \
             patch.object(server, "BILLING_ENFORCED", False):
            client = TestClient(server.app)
            r = client.get("/api/calendar", params={"week_start": "2026-09-13"})
    finally:
        server.app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    upcoming_ids = {u["id"] for u in body["upcoming"]}
    assert "pwo_1" in upcoming_ids
    assert "preq_1" in upcoming_ids
    assert "dec_1" in upcoming_ids
    assert "task_1" in upcoming_ids
    assert "task_done" not in upcoming_ids

    by_type = {u["id"]: u["type"] for u in body["upcoming"]}
    assert by_type["pwo_1"] == "Production"
    assert by_type["preq_1"] == "Procurement"
    assert by_type["dec_1"] == "Decision"
    assert by_type["task_1"] == "Task"

    prod_ev = next(e for e in body["events"] if e.get("source_id") == "pwo_1")
    assert prod_ev["type"] == "Production"
    assert prod_ev["source"] == "deadline"
    assert prod_ev["source_type"] == "production_work_order"
    assert prod_ev["all_day"] is True
