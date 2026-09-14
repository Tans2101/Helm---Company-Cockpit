"""Deal next_step / next_step_date + follow-up signal wiring."""
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DB_NAME", "test_deal_next_step")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import decision_engine as eng  # noqa: E402
import server  # noqa: E402


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


@pytest.fixture
def next_step_api():
    deals = DealStore()
    mock_db = MagicMock()
    mock_db.deals = deals
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
    mock_db.departments.find_one = AsyncMock(return_value={
        "department_id": "dept_sales",
        "workspace_id": "ws1",
        "type": "sales",
        "enabled": True,
    })
    mock_db.department_members = MagicMock()
    mock_db.department_members.find_one = AsyncMock(return_value=None)
    mock_db.department_members.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[]),
    ))
    mock_db.users = MagicMock()
    mock_db.users.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[]),
    ))
    mock_db.financial_entries = MagicMock()
    mock_db.financial_entries.find_one = AsyncMock(return_value=None)

    principal = {
        "user_id": "u_ceo",
        "name": "CEO",
        "email": "ceo@example.com",
        "workspace_id": "ws1",
        "pack": "owner",
        "role": "owner",
    }

    async def as_ceo():
        return principal

    server.app.dependency_overrides[server.get_principal] = as_ceo
    with patch.object(server, "db", mock_db), \
         patch.object(server, "log_activity", new_callable=AsyncMock, return_value=None), \
         patch.object(server, "can_section_write", new_callable=AsyncMock, return_value=True), \
         patch.object(server, "BILLING_ENFORCED", False):
        yield TestClient(server.app), deals
    server.app.dependency_overrides.clear()


def test_next_step_patch_refreshes_updated_at(next_step_api):
    client, deals = next_step_api
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    deals.docs["deal_ns"] = {
        "id": "deal_ns",
        "workspace_id": "ws1",
        "department_id": "dept_sales",
        "name": "Follow-up deal",
        "company": "Acme",
        "value": 5000,
        "stage": "proposal",
        "owner_name": "CEO",
        "owner_user_id": None,
        "close_date": "",
        "next_step": "",
        "next_step_date": "",
        "created_at": stale,
        "updated_at": stale,
    }
    r = client.patch("/api/deals/deal_ns", json={
        "name": "Follow-up deal",
        "company": "Acme",
        "value": 5000,
        "stage": "proposal",
        "owner_name": "CEO",
        "close_date": "",
        "next_step": "Call back Thursday",
        "next_step_date": "2026-09-15",
    })
    assert r.status_code == 200, r.text
    body = r.json()["deal"]
    assert body["next_step"] == "Call back Thursday"
    assert body["next_step_date"] == "2026-09-15"
    assert body["updated_at"] > stale
    assert deals.docs["deal_ns"]["updated_at"] > stale

    # Stalled clock reset: fresh updated_at means no stalled_deal signal
    stalled = eng.detect_stalled_deals([deals.docs["deal_ns"]], now=datetime.now(timezone.utc), days=14)
    assert stalled == []


def test_manual_upcoming_tomorrow_and_missed_yesterday():
    """Acceptance: tomorrow → upcoming_followup; yesterday → missed_followup."""
    today = date(2026, 9, 14)
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    deals = [
        {
            "id": "tomorrow",
            "name": "Tomorrow call",
            "stage": "negotiation",
            "next_step": "Call back Thursday",
            "next_step_date": "2026-09-15",
            "updated_at": now.isoformat(),
        },
        {
            "id": "yesterday",
            "name": "Yesterday send",
            "stage": "proposal",
            "next_step": "Send pricing",
            "next_step_date": "2026-09-13",
            "updated_at": (now - timedelta(days=1)).isoformat(),
        },
    ]
    signals = eng.collect_signals(
        fin={"has_data": False},
        expense_by_month={},
        deals=deals,
        tasks=[],
        updates=[],
        now=now,
    )
    by_id = {s["related_id"]: s for s in signals if s.get("related_id")}
    assert by_id["tomorrow"]["type"] == "upcoming_followup"
    assert by_id["tomorrow"]["severity"] == "low"
    assert "Call back Thursday" in by_id["tomorrow"]["detail"]
    assert by_id["yesterday"]["type"] == "missed_followup"
    assert by_id["yesterday"]["type"] != "stalled_deal"
    assert "Send pricing" in by_id["yesterday"]["detail"]
    assert today == date(2026, 9, 14)  # pinned for readability
