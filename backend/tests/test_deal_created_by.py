"""Deal created_by attribution is set at create and immutable on update."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PRINCIPAL = {
    "user_id": "u_alice",
    "name": "Alice Creator",
    "email": "alice@example.com",
    "workspace_id": "ws1",
    "pack": "owner",
    "role": "owner",
}


class FakeDeals:
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
def client_and_store():
    fake = FakeDeals()
    mock_db = MagicMock()
    mock_db.deals = fake
    mock_db.activities = MagicMock()
    mock_db.activities.insert_one = AsyncMock(return_value=None)
    mock_db.workspaces = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(return_value={
        "workspace_id": "ws1",
        "financial_settings": {"currency": "usd"},
    })
    mock_db.memberships = MagicMock()
    mock_db.memberships.find_one = AsyncMock(return_value={
        "user_id": "u_alice", "workspace_id": "ws1", "status": "active",
        "pack": "owner", "role": "owner", "section_grants": {},
    })
    mock_db.departments = MagicMock()
    mock_db.departments.find_one = AsyncMock(return_value={
        "department_id": "dept_sales",
        "workspace_id": "ws1",
        "type": "sales",
        "name": "Sales",
        "enabled": True,
    })

    async def mock_principal():
        return PRINCIPAL

    server.app.dependency_overrides[server.get_principal] = mock_principal
    with patch.object(server, "db", mock_db), \
         patch.object(server, "log_activity", new_callable=AsyncMock, return_value=None), \
         patch.object(server, "can_section_write", new_callable=AsyncMock, return_value=True), \
         patch.object(server, "_deal_metrics_for_workspace", new_callable=AsyncMock, return_value={
             "open_value": 0, "won_value": 0, "open_count": 0, "by_stage": [],
         }):
        yield TestClient(server.app), fake
    server.app.dependency_overrides.clear()


def test_created_by_set_on_create_and_immutable_on_update(client_and_store):
    client, store = client_and_store
    r = client.post("/api/deals", json={
        "name": "Acme Deal",
        "company": "Acme",
        "value": 10000,
        "stage": "lead",
        "owner_name": "Alice Creator",
        "close_date": "",
    })
    assert r.status_code == 200, r.text
    deal = r.json()["deal"]
    assert deal["created_by_user_id"] == "u_alice"
    assert deal["created_by_name"] == "Alice Creator"
    assert deal["department_id"] == "dept_sales"
    deal_id = deal["id"]

    r2 = client.patch(f"/api/deals/{deal_id}", json={
        "name": "Acme Deal",
        "company": "Acme",
        "value": 10000,
        "stage": "qualified",
        "owner_name": "Bob Owner",
        "close_date": "",
    })
    assert r2.status_code == 200, r2.text
    updated = r2.json()["deal"]
    assert updated["owner_name"] == "Bob Owner"
    assert updated["created_by_user_id"] == "u_alice"
    assert updated["created_by_name"] == "Alice Creator"
    stored = store.docs[deal_id]
    assert stored["created_by_user_id"] == "u_alice"
    assert stored["created_by_name"] == "Alice Creator"
    assert stored["owner_name"] == "Bob Owner"
    # Ensure update $set never wrote created_by_*
    assert "created_by_user_id" in stored
    assert stored["created_by_name"] == "Alice Creator"
