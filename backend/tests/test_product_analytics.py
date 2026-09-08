"""First-party product_events logging — no third-party analytics."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_product_analytics")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import product_analytics as pa  # noqa: E402
import server  # noqa: E402


@pytest.mark.asyncio
async def test_log_event_inserts_without_pii_fields():
    inserted = []

    mock_db = MagicMock()
    mock_db.product_events.insert_one = AsyncMock(side_effect=lambda doc: inserted.append(doc))

    ok = await pa.log_event(mock_db, "ws_1", "u_1", "department_enabled", {"department": "sales"})
    assert ok is True
    assert len(inserted) == 1
    doc = inserted[0]
    assert doc["workspace_id"] == "ws_1"
    assert doc["user_id"] == "u_1"
    assert doc["event_type"] == "department_enabled"
    assert doc["metadata"]["department"] == "sales"
    assert "email" not in doc
    assert "created_at" in doc


@pytest.mark.asyncio
async def test_log_event_failure_never_raises():
    mock_db = MagicMock()
    mock_db.product_events.insert_one = AsyncMock(side_effect=RuntimeError("mongo down"))
    ok = await pa.log_event(mock_db, "ws_1", "u_1", "ask_helm_used", {})
    assert ok is False


@pytest.mark.asyncio
async def test_log_event_once_does_not_duplicate():
    mock_db = MagicMock()
    mock_db.product_events.find_one = AsyncMock(return_value={"_id": "x"})
    mock_db.product_events.insert_one = AsyncMock()
    ok = await pa.log_event_once(
        mock_db, "ws_1", "u_1", pa.EVENT_ONBOARDING_STEP, {"step": "financials"},
        once_key="financials",
    )
    assert ok is False
    mock_db.product_events.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_emit_billing_funnel_trial_then_convert_then_cancel():
    inserted = []
    mock_db = MagicMock()
    mock_db.product_events.insert_one = AsyncMock(side_effect=lambda doc: inserted.append(doc["event_type"]))

    await pa.emit_billing_funnel(mock_db, "ws", "u", None, "trialing", "starter")
    await pa.emit_billing_funnel(mock_db, "ws", "u", "trialing", "trialing", "starter")
    await pa.emit_billing_funnel(mock_db, "ws", "u", "trialing", "active", "starter")
    await pa.emit_billing_funnel(mock_db, "ws", "u", "active", "canceled", "starter")
    assert inserted == [
        pa.EVENT_TRIAL_STARTED,
        pa.EVENT_TRIAL_CONVERTED,
        pa.EVENT_SUBSCRIPTION_CANCELLED,
    ]


@pytest.mark.asyncio
async def test_analytics_summary_aggregates():
    mock_db = MagicMock()
    mock_db.workspaces.count_documents = AsyncMock(return_value=4)

    def fake_aggregate(pipeline):
        match = (pipeline[0].get("$match") or {}).get("event_type")
        if match == pa.EVENT_DEPARTMENT_ENABLED:
            return MagicMock(to_list=AsyncMock(return_value=[
                {"_id": "sales", "count": 3},
                {"_id": "hr", "count": 1},
            ]))
        if match == pa.EVENT_DEPARTMENT_PAGE_VIEWED:
            return MagicMock(to_list=AsyncMock(return_value=[
                {"_id": "sales", "count": 10},
            ]))
        if match == pa.EVENT_ONBOARDING_STEP:
            return MagicMock(to_list=AsyncMock(return_value=[
                {"_id": "financials", "workspaces": 2},
                {"_id": "invite", "workspaces": 1},
            ]))
        return MagicMock(to_list=AsyncMock(return_value=[]))

    mock_db.product_events.aggregate = fake_aggregate

    async def fake_distinct(field, filt):
        et = filt["event_type"]
        if et == pa.EVENT_TRIAL_STARTED:
            return ["ws_a", "ws_b"]
        if et == pa.EVENT_TRIAL_CONVERTED:
            return ["ws_a"]
        if et == pa.EVENT_SUBSCRIPTION_CANCELLED:
            return []
        return []

    mock_db.product_events.distinct = fake_distinct
    mock_db.product_events.count_documents = AsyncMock(side_effect=[7, 12])

    summary = await pa.analytics_summary(mock_db)
    assert summary["total_workspaces"] == 4
    assert summary["department_enabled_counts"]["sales"] == 3
    assert summary["onboarding_step_workspaces"]["financials"] == 2
    assert summary["onboarding_step_completion_rates"]["financials"] == 0.5
    assert summary["trial_started_workspaces"] == 2
    assert summary["trial_converted_workspaces"] == 1
    assert summary["trial_to_paid_conversion_rate"] == 0.5
    assert summary["ai_extract_used"] == 7
    assert summary["ask_helm_used"] == 12


def test_analytics_endpoint_forbidden_for_workspace_admin():
    async def mock_principal():
        return {
            "user_id": "u_admin",
            "email": "ceo@example.com",
            "name": "CEO",
            "workspace_id": "ws_1",
            "role": "owner",
            "pack": "owner",
        }

    server.app.dependency_overrides[server.get_principal] = mock_principal
    with patch.object(server, "ANALYTICS_ADMIN_EMAIL", "tansherdhawan@gmail.com"):
        client = TestClient(server.app)
        r = client.get("/api/internal/analytics-summary")
    server.app.dependency_overrides.clear()
    assert r.status_code == 403


def test_analytics_endpoint_ok_for_operator_email():
    async def mock_principal():
        return {
            "user_id": "u_tansh",
            "email": "tansherdhawan@gmail.com",
            "name": "Tansh",
            "workspace_id": "ws_1",
            "role": "owner",
            "pack": "owner",
        }

    async def fake_summary(_db):
        return {"total_workspaces": 2, "trial_to_paid_conversion_rate": 0.0}

    server.app.dependency_overrides[server.get_principal] = mock_principal
    with patch.object(server, "ANALYTICS_ADMIN_EMAIL", "tansherdhawan@gmail.com"), patch.object(
        server.helm_analytics, "analytics_summary", new=fake_summary
    ):
        client = TestClient(server.app)
        r = client.get("/api/internal/analytics-summary")
    server.app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    assert r.json()["total_workspaces"] == 2
