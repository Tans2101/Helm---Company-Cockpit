"""Won deal → automatic revenue entry + production prompt."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DB_NAME", "test_deal_won")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PRINCIPAL = {
    "user_id": "u_ceo",
    "name": "CEO",
    "email": "ceo@example.com",
    "workspace_id": "ws1",
    "pack": "owner",
    "role": "owner",
}


class DocStore:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                ok = True
                for k, v in query.items():
                    if isinstance(v, dict):
                        ok = False
                        break
                    if r.get(k) != v:
                        ok = False
                        break
                if ok:
                    return {k: v for k, v in r.items() if k != "_id"}
        # support simple equality including source_deal_id
        for r in self.rows:
            match = True
            for k, v in query.items():
                if r.get(k) != v:
                    match = False
                    break
            if match:
                return {k: val for k, val in r.items() if k != "_id"}
        return None

    async def insert_one(self, doc):
        # Enforce sparse unique source_deal_id within workspace (like Mongo index)
        sid = doc.get("source_deal_id")
        if sid:
            for r in self.rows:
                if r.get("workspace_id") == doc.get("workspace_id") and r.get("source_deal_id") == sid:
                    raise Exception("E11000 duplicate key error collection source_deal_id")
        self.rows.append(dict(doc))
        return MagicMock()

    async def update_one(self, query, update):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                r.update(update.get("$set") or {})
                return MagicMock(matched_count=1)
        return MagicMock(matched_count=0)

    async def insert_one_deal(self, doc):
        self.rows.append(dict(doc))


class DealStore:
    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        self.docs[doc["id"]] = dict(doc)
        return MagicMock()

    async def find_one(self, filt, proj=None):
        d = self.docs.get(filt.get("id"))
        if not d or d.get("workspace_id") != filt.get("workspace_id"):
            return None
        return dict(d)

    async def update_one(self, filt, update):
        d = self.docs.get(filt.get("id"))
        if not d:
            return MagicMock(matched_count=0)
        if "$set" in update:
            d.update(update["$set"])
        return MagicMock(matched_count=1)

    async def delete_one(self, filt):
        self.docs.pop(filt.get("id"), None)
        return MagicMock(deleted_count=1)


@pytest.fixture
def won_api():
    deals = DealStore()
    entries = DocStore()
    mock_db = MagicMock()
    mock_db.deals = deals
    mock_db.financial_entries = entries
    mock_db.activities = MagicMock()
    mock_db.activities.insert_one = AsyncMock(return_value=None)
    mock_db.workspaces = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(return_value={
        "workspace_id": "ws1",
        "financial_settings": {"currency": "usd"},
    })
    mock_db.memberships = MagicMock()
    mock_db.memberships.find_one = AsyncMock(return_value={
        "user_id": "u_ceo", "workspace_id": "ws1", "status": "active",
        "pack": "owner", "role": "owner", "section_grants": {},
    })
    mock_db.departments = MagicMock()

    async def dept_find_one(query, projection=None):
        dtype = query.get("type")
        if dtype == "sales" or query.get("department_id") == "dept_sales":
            return {
                "department_id": "dept_sales",
                "workspace_id": "ws1",
                "type": "sales",
                "name": "Sales",
                "enabled": True,
            }
        if dtype == "accounting_finance":
            return {
                "department_id": "dept_fin",
                "workspace_id": "ws1",
                "type": "accounting_finance",
                "name": "Finance",
                "enabled": True,
            }
        if dtype == "production":
            return {
                "department_id": "dept_prod",
                "workspace_id": "ws1",
                "type": "production",
                "name": "Production",
                "enabled": True,
            }
        return None

    mock_db.departments.find_one = AsyncMock(side_effect=dept_find_one)
    mock_db.department_members = MagicMock()
    mock_db.department_members.find_one = AsyncMock(return_value=None)
    mock_db.department_members.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[]),
    ))
    mock_db.users = MagicMock()
    mock_db.users.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[]),
    ))

    async def as_ceo():
        return PRINCIPAL

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db), \
         patch.object(server, "log_activity", new_callable=AsyncMock, return_value=None), \
         patch.object(server, "can_section_write", new_callable=AsyncMock, return_value=True), \
         patch.object(server, "BILLING_ENFORCED", False):
        client = TestClient(server.app)
        yield client, deals, entries, mock_db
    server.app.dependency_overrides.clear()


def _create_deal(client, **overrides):
    body = {
        "name": "Acme Enterprise",
        "company": "Acme Corp",
        "value": 25000,
        "stage": "negotiation",
        "owner_name": "CEO",
        "close_date": "2026-09-20",
    }
    body.update(overrides)
    r = client.post("/api/deals", json=body)
    assert r.status_code == 200, r.text
    return r.json()["deal"]


def test_won_creates_revenue_entry_and_production_prompt(won_api):
    client, deals, entries, mock_db = won_api
    deal = _create_deal(client)
    r = client.patch(f"/api/deals/{deal['id']}", json={
        "name": deal["name"],
        "company": deal["company"],
        "value": deal["value"],
        "stage": "won",
        "owner_name": deal["owner_name"],
        "close_date": deal["close_date"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["production_prompt"] is True
    assert body["production_prefill"]["reference"] == "Acme Enterprise"
    assert body["production_prefill"]["customer"] == "Acme Corp"
    assert body["production_prefill"]["source_deal_id"] == deal["id"]
    entry = body["financial_entry"]
    assert entry is not None
    assert entry["type"] == "revenue"
    assert entry["category"] == "Sales"
    assert entry["source"] == "deal"
    assert entry["source_deal_id"] == deal["id"]
    assert entry["amount"] == 25000
    assert entry["name"] == "Acme Enterprise"
    assert entry["month"] == "2026-09"
    assert len(entries.rows) == 1


def test_resaving_won_does_not_duplicate_entry(won_api):
    client, deals, entries, *_ = won_api
    deal = _create_deal(client)
    payload = {
        "name": deal["name"],
        "company": deal["company"],
        "value": deal["value"],
        "stage": "won",
        "owner_name": deal["owner_name"],
        "close_date": deal["close_date"],
    }
    assert client.patch(f"/api/deals/{deal['id']}", json=payload).status_code == 200
    assert len(entries.rows) == 1

    # Unrelated edit while already won — no new entry, no production prompt
    payload["value"] = 26000
    r2 = client.patch(f"/api/deals/{deal['id']}", json=payload)
    assert r2.status_code == 200
    assert r2.json()["production_prompt"] is False
    assert r2.json()["financial_entry"] is None
    assert len(entries.rows) == 1

    # Move away and win again — still only one entry
    payload["stage"] = "negotiation"
    payload["value"] = 25000
    assert client.patch(f"/api/deals/{deal['id']}", json=payload).status_code == 200
    payload["stage"] = "won"
    r3 = client.patch(f"/api/deals/{deal['id']}", json=payload)
    assert r3.status_code == 200, r3.text
    assert r3.json()["production_prompt"] is True
    assert len(entries.rows) == 1
    assert r3.json()["financial_entry"]["source_deal_id"] == deal["id"]


def test_no_production_prompt_when_production_disabled(won_api):
    client, deals, entries, mock_db = won_api

    async def dept_find_one(query, projection=None):
        dtype = query.get("type")
        if dtype == "production":
            return None
        if dtype == "sales" or query.get("department_id") == "dept_sales":
            return {
                "department_id": "dept_sales",
                "workspace_id": "ws1",
                "type": "sales",
                "enabled": True,
            }
        if dtype == "accounting_finance":
            return {
                "department_id": "dept_fin",
                "workspace_id": "ws1",
                "type": "accounting_finance",
                "enabled": True,
            }
        return None

    mock_db.departments.find_one = AsyncMock(side_effect=dept_find_one)
    deal = _create_deal(client)
    r = client.patch(f"/api/deals/{deal['id']}", json={
        "name": deal["name"],
        "company": deal["company"],
        "value": deal["value"],
        "stage": "won",
        "owner_name": deal["owner_name"],
        "close_date": "",
    })
    assert r.status_code == 200, r.text
    assert r.json()["production_prompt"] is False
    assert r.json()["production_prefill"] is None
    assert r.json()["financial_entry"]["source"] == "deal"
    assert len(entries.rows) == 1


def test_deal_revenue_month_helper():
    from datetime import datetime, timezone
    now = datetime(2026, 3, 15, tzinfo=timezone.utc)
    assert server._deal_revenue_month("2026-09-20", now=now) == "2026-09"
    assert server._deal_revenue_month("", now=now) == "2026-03"
    assert server._deal_revenue_month("not-a-date", now=now) == "2026-03"
