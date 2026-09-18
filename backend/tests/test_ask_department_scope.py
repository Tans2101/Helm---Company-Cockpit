"""Ask Helm context respects department membership (Sales/HR), CEO sees all."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_ask_department_scope")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import departments_catalog as dept_catalog  # noqa: E402
import server  # noqa: E402
from server import ask_context_for_synthesis  # noqa: E402


def _company():
    return {
        "name": "Acme",
        "stage": "Seed",
        "employees": 2,
        "people": {"people": [{"id": "p1"}]},
        "decisions": [{"title": "Hire", "status": "pending"}],
        "telemetry_manual": {"risks": []},
        "workspace_id": "ws_ask",
        "plan": "starter",
    }


def _deals():
    return [
        {"id": "d1", "stage": "negotiation", "value": 50000, "title": "Big Deal"},
        {"id": "d2", "stage": "won", "value": 10000, "title": "Won Deal"},
    ]


def _onboarding():
    return [
        {"id": "o1", "hire_name": "Alex", "overall_status": "in_progress"},
    ]


def test_ask_context_restricts_sales_and_hr_when_not_visible():
    ctx = ask_context_for_synthesis(
        _company(),
        {},
        deals=_deals(),
        sales_tracked=True,
        onboarding_instances=_onboarding(),
        hr_tracked=True,
        financials_visible=False,
        sales_visible=False,
        hr_visible=False,
    )
    assert ctx["pipeline"]["access"] == "restricted"
    assert "50000" not in str(ctx["pipeline"])
    assert "Big Deal" not in str(ctx["pipeline"])
    assert ctx["onboarding"]["access"] == "restricted"
    assert "Alex" not in str(ctx["onboarding"])
    # Production / Legal / etc. are not loaded into Ask context at all.
    assert "production" not in ctx
    assert "legal" not in ctx
    assert "procurement" not in ctx
    assert "maintenance" not in ctx


def test_ask_context_includes_sales_and_hr_when_visible():
    ctx = ask_context_for_synthesis(
        _company(),
        {},
        deals=_deals(),
        sales_tracked=True,
        onboarding_instances=_onboarding(),
        hr_tracked=True,
        financials_visible=False,
        sales_visible=True,
        hr_visible=True,
    )
    assert ctx["pipeline"].get("access") != "restricted"
    assert ctx["pipeline"]["tracked"] is True
    assert ctx["pipeline"]["deal_count"] >= 1
    assert ctx["onboarding"].get("access") != "restricted"
    assert ctx["onboarding"]["instance_count"] == 1


@pytest.mark.asyncio
async def test_ask_helm_scopes_deals_and_onboarding_by_membership():
    principal = {
        "user_id": "u_sales",
        "workspace_id": "ws_ask",
        "pack": "member",
        "role": "member",
        "email": "sales@example.com",
        "name": "Sales",
    }
    ws = _company()
    mock_db = MagicMock()
    mock_db.chat_messages.insert_one = AsyncMock(return_value=None)

    deals_cursor = MagicMock()
    deals_cursor.to_list = AsyncMock(return_value=[
        {"id": "d1", "stage": "negotiation", "value": 12000, "department_id": "dept_sales"},
    ])
    mock_db.deals.find = MagicMock(return_value=deals_cursor)

    onboarding_cursor = MagicMock()
    onboarding_cursor.to_list = AsyncMock(return_value=[])
    mock_db.hr_onboarding_instances.find = MagicMock(return_value=onboarding_cursor)

    captured = {}

    async def _capture_stream(system, message):
        captured["system"] = system
        yield "ok"

    with patch.object(server, "get_ws", new=AsyncMock(return_value=ws)), \
            patch.object(server, "can_access_financials", new=AsyncMock(return_value=False)), \
            patch.object(server, "db", mock_db), \
            patch.object(server, "_product_event", new=AsyncMock()), \
            patch.object(server.helm_llm, "anthropic_configured", return_value=True), \
            patch.object(server.helm_llm, "stream_text", side_effect=_capture_stream), \
            patch.object(server.plan_usage, "acquire_period_ask_slot", new=AsyncMock(return_value=True)), \
            patch.object(server.plan_usage, "current_usage_period", return_value={
                "key": "2026-09-01",
                "start": __import__("datetime").datetime(2026, 9, 1, tzinfo=__import__("datetime").timezone.utc),
                "end": __import__("datetime").datetime(2026, 10, 1, tzinfo=__import__("datetime").timezone.utc),
            }), \
            patch.object(server, "BILLING_ENFORCED", False), \
            patch.object(server.dept_migrate, "get_enabled_department", new=AsyncMock(side_effect=lambda *_a, **k: (
                {"department_id": "dept_sales", "type": dept_catalog.TYPE_SALES}
                if (k.get("dept_type") or (_a[2] if len(_a) > 2 else None)) == dept_catalog.TYPE_SALES
                else {"department_id": "dept_hr", "type": dept_catalog.TYPE_HR}
            ))), \
            patch.object(server.dept_access, "accessible_department_ids", new=AsyncMock(side_effect=lambda *_a, **k: (
                ["dept_sales"] if (_a[2] if len(_a) > 2 else k.get("dept_type")) == dept_catalog.TYPE_SALES else []
            ))):
        resp = await server.ask_helm(
            server.AskInput(message="How is the pipeline looking?"),
            principal,
        )
        chunks = []
        async for chunk in resp.body_iterator:
            chunks.append(chunk if isinstance(chunk, str) else chunk.decode())

    assert "".join(chunks) == "ok"
    system = captured["system"]
    assert "12000" in system or "deal_count" in system
    assert '"access": "restricted"' in system or "'access': 'restricted'" in system
    # HR restricted for this sales-only member
    assert "HR onboarding data is not shared" in system
    # No production/legal queues in snapshot
    assert "production_work_orders" not in system
    assert "legal_matters" not in system
    deal_filt = mock_db.deals.find.call_args[0][0]
    assert deal_filt.get("department_id") == {"$in": ["dept_sales"]}
    # HR query should not run with real rows (hr_visible False → no find call with data)
    # When hr_visible is False we skip the find entirely.
    mock_db.hr_onboarding_instances.find.assert_not_called()


@pytest.mark.asyncio
async def test_ask_helm_ceo_sees_sales_and_hr_unfiltered():
    principal = {
        "user_id": "u_ceo",
        "workspace_id": "ws_ask",
        "pack": "owner",
        "role": "owner",
        "email": "ceo@example.com",
        "name": "CEO",
    }
    ws = _company()
    mock_db = MagicMock()
    mock_db.chat_messages.insert_one = AsyncMock(return_value=None)

    deals_cursor = MagicMock()
    deals_cursor.to_list = AsyncMock(return_value=_deals())
    mock_db.deals.find = MagicMock(return_value=deals_cursor)

    onboarding_cursor = MagicMock()
    onboarding_cursor.to_list = AsyncMock(return_value=_onboarding())
    mock_db.hr_onboarding_instances.find = MagicMock(return_value=onboarding_cursor)

    captured = {}

    async def _capture_stream(system, message):
        captured["system"] = system
        yield "ceo-ok"

    with patch.object(server, "get_ws", new=AsyncMock(return_value=ws)), \
            patch.object(server, "can_access_financials", new=AsyncMock(return_value=True)), \
            patch.object(server, "compute_financials", new=AsyncMock(return_value={
                "mrr_value": 1, "burn_value": 1, "cash_entered": False,
                "mrr_known": False, "burn_known": False, "currency": "usd",
            })), \
            patch.object(server, "db", mock_db), \
            patch.object(server, "_product_event", new=AsyncMock()), \
            patch.object(server.helm_llm, "anthropic_configured", return_value=True), \
            patch.object(server.helm_llm, "stream_text", side_effect=_capture_stream), \
            patch.object(server.plan_usage, "acquire_period_ask_slot", new=AsyncMock(return_value=True)), \
            patch.object(server.plan_usage, "current_usage_period", return_value={
                "key": "2026-09-01",
                "start": __import__("datetime").datetime(2026, 9, 1, tzinfo=__import__("datetime").timezone.utc),
                "end": __import__("datetime").datetime(2026, 10, 1, tzinfo=__import__("datetime").timezone.utc),
            }), \
            patch.object(server, "BILLING_ENFORCED", False), \
            patch.object(server.dept_migrate, "get_enabled_department", new=AsyncMock(return_value={
                "department_id": "dept_x", "type": "x",
            })), \
            patch.object(server.dept_access, "accessible_department_ids", new=AsyncMock(return_value=None)):
        resp = await server.ask_helm(
            server.AskInput(message="Give me a company pulse"),
            principal,
        )
        async for _ in resp.body_iterator:
            pass

    system = captured["system"]
    assert "Sales pipeline is not shared" not in system
    assert "HR onboarding data is not shared" not in system
    # CEO bypass: filter has no department_id constraint
    deal_filt = mock_db.deals.find.call_args[0][0]
    assert "department_id" not in deal_filt
    mock_db.hr_onboarding_instances.find.assert_called_once()
