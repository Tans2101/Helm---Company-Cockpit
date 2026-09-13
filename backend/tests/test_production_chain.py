"""Production work-order API tests."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_production_chain")

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

OUTSIDER = {
    "user_id": "u_out",
    "email": "out@acme.com",
    "name": "Out",
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

PROD_DEPT = {
    "department_id": "dept_prod",
    "workspace_id": "ws_test",
    "type": "production",
    "name": "Production",
    "enabled": True,
}


def _match(doc: dict, query: dict) -> bool:
    if not query:
        return True
    for k, v in query.items():
        if k == "$or":
            if not any(_match(doc, clause) for clause in v):
                return False
            continue
        actual = doc.get(k)
        if isinstance(v, dict):
            if "$in" in v:
                if actual not in v["$in"]:
                    return False
            elif "$gt" in v:
                if not (actual is not None and actual > v["$gt"]):
                    return False
            else:
                return False
        elif actual != v:
            return False
    return True


class DocStore:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if _match(r, query):
                return {k: v for k, v in r.items() if k != "_id"}
        return None

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if _match(r, query or {})]
        state = {"sort": None}

        class C:
            def sort(self, field, direction=1):
                state["sort"] = (field, direction)
                return self

            async def to_list(self, n):
                items = list(matched)
                if state["sort"]:
                    field, direction = state["sort"]
                    items.sort(key=lambda x: x.get(field) or 0, reverse=direction == -1)
                return items[:n]

        return C()

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def update_one(self, query, update):
        for r in self.rows:
            if _match(r, query):
                r.update(update.get("$set") or {})
                return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)

    async def delete_one(self, query):
        before = len(self.rows)
        self.rows = [r for r in self.rows if not _match(r, query)]
        return MagicMock(deleted_count=before - len(self.rows))


@pytest.fixture
def prod_api():
    templates = DocStore()
    orders = DocStore()
    progress = DocStore()
    procurement = DocStore()
    dept_members = [
        {"department_id": "dept_prod", "user_id": "u_mem", "role": "member"},
        {"department_id": "dept_prod", "user_id": "u_lead", "role": "lead"},
    ]

    async def dept_find_one(query, projection=None):
        if query.get("type") == "production" or query.get("department_id") == "dept_prod":
            if query.get("workspace_id") in (None, "ws_test"):
                return dict(PROD_DEPT)
        return None

    async def mem_find_one(query, projection=None):
        for m in dept_members:
            if all(m.get(k) == v for k, v in query.items()):
                return dict(m)
        return None

    mock_db = MagicMock()
    mock_db.departments.find_one = AsyncMock(side_effect=dept_find_one)
    mock_db.department_members.find_one = AsyncMock(side_effect=mem_find_one)
    mock_db.production_stage_templates = templates
    mock_db.production_work_orders = orders
    mock_db.production_stage_progress = progress
    mock_db.procurement_requests = procurement
    mock_db.users.find_one = AsyncMock(
        return_value={"name": "Mem", "email": "mem@acme.com", "picture": None},
    )
    attach_users_in_find(mock_db.users)

    async def as_ceo():
        return CEO

    async def as_outsider():
        return OUTSIDER

    async def as_member():
        return MEMBER

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db):
        client = TestClient(server.app)
        yield client, templates, orders, progress, as_ceo, as_outsider, as_member
    server.app.dependency_overrides.clear()


def _seed_two_stages(client):
    a = client.post("/api/production/stages", json={"name": "Prep"}).json()["stage"]
    b = client.post("/api/production/stages", json={"name": "Assemble"}).json()["stage"]
    return a, b


def test_outsider_gets_403(prod_api):
    client, templates, orders, progress, as_ceo, as_outsider, as_member = prod_api
    server.app.dependency_overrides[server.get_principal] = as_outsider
    assert client.get("/api/production/stages").status_code == 403
    assert client.post("/api/production/stages", json={"name": "Cut"}).status_code == 403
    assert client.get("/api/production/work-orders").status_code == 403


def test_ceo_create_list_reorder_delete_templates(prod_api):
    client, templates, orders, progress, *_ = prod_api
    r = client.post("/api/production/stages", json={"name": "Prep"})
    assert r.status_code == 200, r.text
    sid1 = r.json()["stage"]["id"]
    assert "status" not in r.json()["stage"]
    assert "default_assigned_user_ids" in r.json()["stage"]
    sid2 = client.post("/api/production/stages", json={"name": "Assemble"}).json()["stage"]["id"]

    listed = client.get("/api/production/stages").json()["stages"]
    assert [s["name"] for s in listed] == ["Prep", "Assemble"]

    rr = client.patch("/api/production/stages/reorder", json={"stage_ids": [sid2, sid1]})
    assert rr.status_code == 200, rr.text
    listed2 = client.get("/api/production/stages").json()["stages"]
    assert [s["name"] for s in listed2] == ["Assemble", "Prep"]

    assert client.delete(f"/api/production/stages/{sid2}").status_code == 200
    left = client.get("/api/production/stages").json()["stages"]
    assert [s["name"] for s in left] == ["Prep"]
    assert left[0]["order"] == 0


def test_member_cannot_edit_templates_but_can_update_progress(prod_api):
    client, templates, orders, progress, as_ceo, as_outsider, as_member = prod_api
    a, _b = _seed_two_stages(client)
    wo = client.post(
        "/api/production/work-orders",
        json={"reference": "Order #1"},
    ).json()["work_order"]

    server.app.dependency_overrides[server.get_principal] = as_member
    assert client.post("/api/production/stages", json={"name": "X"}).status_code == 403
    assert client.patch(f"/api/production/stages/{a['id']}", json={"name": "Renamed"}).status_code == 403
    assert client.delete(f"/api/production/stages/{a['id']}").status_code == 403

    ok = client.patch(
        f"/api/production/work-orders/{wo['id']}/stage",
        json={"status": "in_progress", "assigned_user_ids": ["u_mem"]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["work_order"]["current_progress"]["status"] == "in_progress"
    assert "u_mem" in ok.json()["work_order"]["current_progress"]["assigned_user_ids"]


def test_two_work_orders_advance_independently(prod_api):
    client, templates, orders, progress, *_ = prod_api
    a, b = _seed_two_stages(client)

    wo1 = client.post("/api/production/work-orders", json={"reference": "Order #1"}).json()["work_order"]
    wo2 = client.post("/api/production/work-orders", json={"reference": "Order #2"}).json()["work_order"]
    assert wo1["current_stage_id"] == a["id"]
    assert wo2["current_stage_id"] == a["id"]
    assert wo1["current_progress"]["status"] == "not_started"
    assert wo1["current_progress"]["entered_at"]
    assert wo1["current_progress"]["exited_at"] is None

    adv1 = client.patch(f"/api/production/work-orders/{wo1['id']}/advance")
    assert adv1.status_code == 200, adv1.text
    moved = adv1.json()["work_order"]
    assert moved["current_stage_id"] == b["id"]
    assert moved["status"] == "active"
    assert moved["current_progress"]["stage_id"] == b["id"]
    assert moved["current_progress"]["status"] == "in_progress"
    assert moved["current_progress"]["entered_at"]
    assert moved["current_progress"]["exited_at"] is None

    closed = next(
        p for p in progress.rows
        if p["work_order_id"] == wo1["id"] and p["stage_id"] == a["id"]
    )
    assert closed["status"] == "done"
    assert closed["exited_at"]

    listed = client.get("/api/production/work-orders").json()["work_orders"]
    by_id = {o["id"]: o for o in listed}
    assert by_id[wo2["id"]]["current_stage_id"] == a["id"]
    assert by_id[wo1["id"]]["current_stage_id"] == b["id"]


def test_advance_past_last_stage_marks_done(prod_api):
    client, templates, orders, progress, *_ = prod_api
    _seed_two_stages(client)
    wo = client.post("/api/production/work-orders", json={"reference": "Final"}).json()["work_order"]

    client.patch(f"/api/production/work-orders/{wo['id']}/advance")
    done = client.patch(f"/api/production/work-orders/{wo['id']}/advance")
    assert done.status_code == 200, done.text
    body = done.json()["work_order"]
    assert body["status"] == "done"
    assert body["completed_at"]
    assert body["current_progress"]["status"] == "done"
    assert body["current_progress"]["exited_at"]

    again = client.patch(f"/api/production/work-orders/{wo['id']}/advance")
    assert again.status_code == 400


def test_blocked_requires_category(prod_api):
    client, *_ = prod_api
    _seed_two_stages(client)
    wo = client.post("/api/production/work-orders", json={"reference": "Block me"}).json()["work_order"]

    bad = client.patch(
        f"/api/production/work-orders/{wo['id']}/stage",
        json={"status": "blocked"},
    )
    assert bad.status_code == 400
    assert "blocked_reason" in bad.json()["detail"]

    bad2 = client.patch(
        f"/api/production/work-orders/{wo['id']}/stage",
        json={"status": "blocked", "blocked_reason": {"detail": "no parts"}},
    )
    assert bad2.status_code == 400

    ok = client.patch(
        f"/api/production/work-orders/{wo['id']}/stage",
        json={
            "status": "blocked",
            "blocked_reason": {"category": "material", "detail": "Waiting on steel"},
        },
    )
    assert ok.status_code == 200, ok.text
    reason = ok.json()["work_order"]["current_progress"]["blocked_reason"]
    assert reason["category"] == "material"
    assert "steel" in reason["detail"]


def test_patch_work_order_fields(prod_api):
    client, *_ = prod_api
    _seed_two_stages(client)
    wo = client.post(
        "/api/production/work-orders",
        json={"reference": "Order #9", "priority": "high", "customer": "Acme"},
    ).json()["work_order"]
    assert wo["priority"] == "high"

    patched = client.patch(
        f"/api/production/work-orders/{wo['id']}",
        json={"product": "Widget", "quantity": 12, "due_date": "2026-10-01"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()["work_order"]
    assert body["product"] == "Widget"
    assert body["quantity"] == 12
    assert body["due_date"] == "2026-10-01"


def test_cannot_create_work_order_without_stages(prod_api):
    client, *_ = prod_api
    r = client.post("/api/production/work-orders", json={"reference": "Orphan"})
    assert r.status_code == 400


def test_cannot_delete_stage_with_active_work_order(prod_api):
    client, *_ = prod_api
    a, _b = _seed_two_stages(client)
    client.post("/api/production/work-orders", json={"reference": "Hold"})
    denied = client.delete(f"/api/production/stages/{a['id']}")
    assert denied.status_code == 400
