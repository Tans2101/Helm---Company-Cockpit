"""Null-vs-zero for MRR/runway: expense-only ≠ $0 MRR; profitable ≠ missing runway."""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_financials_null_vs_zero")

import server  # noqa: E402


def _entries_cursor(rows):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows)
    return cursor


def _run_compute(entries, settings):
    server._FINANCIALS_CACHE.clear()
    mock_db = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(
        return_value={"financial_settings": settings},
    )
    mock_db.financial_entries.find = MagicMock(return_value=_entries_cursor(entries))
    with patch.object(server, "db", mock_db):
        return asyncio.run(server.compute_financials("ws_test", bypass_cache=True))


def test_format_runway_display_states():
    assert server.format_runway_display({"runway_months": 12.5}) == "12.5mo"
    assert server.format_runway_display({"runway_months": None, "runway_no_burn": True}) == (
        server.RUNWAY_NO_BURN_LABEL
    )
    assert server.format_runway_display({"runway_months": None}) == "Add data"
    assert server.format_runway_display({"runway_months": None}, missing="—") == "—"


def test_expense_only_ledger_does_not_confirm_zero_mrr():
    fin = _run_compute(
        [
            {
                "type": "expense",
                "category": "Cloud",
                "amount": 5000,
                "month": "2026-08",
                "recurring": True,
            },
            {
                "type": "expense",
                "category": "Cloud",
                "amount": 5000,
                "month": "2026-09",
                "recurring": True,
            },
        ],
        {"cash": 100000, "currency": "usd"},
    )
    assert fin["mrr_known"] is False
    assert fin["mrr"] == "—"
    assert fin["mrr_value"] is None
    assert fin["burn_known"] is True
    assert fin["has_data"] is True


def test_profitable_company_runway_is_not_add_data():
    fin = _run_compute(
        [
            {
                "type": "revenue",
                "category": "Subscriptions",
                "amount": 20000,
                "month": "2026-07",
                "recurring": True,
            },
            {
                "type": "revenue",
                "category": "Subscriptions",
                "amount": 20000,
                "month": "2026-08",
                "recurring": True,
            },
            {
                "type": "revenue",
                "category": "Subscriptions",
                "amount": 20000,
                "month": "2026-09",
                "recurring": True,
            },
            {
                "type": "expense",
                "category": "Ops",
                "amount": 8000,
                "month": "2026-07",
                "recurring": True,
            },
            {
                "type": "expense",
                "category": "Ops",
                "amount": 8000,
                "month": "2026-08",
                "recurring": True,
            },
            {
                "type": "expense",
                "category": "Ops",
                "amount": 8000,
                "month": "2026-09",
                "recurring": True,
            },
        ],
        {"cash": 250000, "currency": "usd"},
    )
    assert fin["runway_months"] is None
    assert fin["runway_no_burn"] is True
    assert server.format_runway_display(fin) == server.RUNWAY_NO_BURN_LABEL
    assert fin["mrr_known"] is True


def test_empty_ledger_runway_still_missing():
    fin = _run_compute([], {"cash": 250000, "currency": "usd"})
    assert fin["runway_months"] is None
    assert fin["runway_no_burn"] is False
    assert fin["mrr_known"] is False
    assert server.format_runway_display(fin) == "Add data"


def test_synthesis_skips_runway_unknown_when_no_burn():
    payload = server.financials_for_synthesis(
        {
            "cash_entered": True,
            "cash_value": 250000,
            "mrr_known": True,
            "mrr_value": 20000,
            "burn_known": True,
            "burn_value": -12000,
            "runway_months": None,
            "runway_no_burn": True,
            "currency": "usd",
        }
    )
    assert "runway_not_computable" not in payload["unknown_fields"]
    assert payload["runway_no_burn"] is True
    assert "cash is growing" in payload["instructions_for_missing_data"]


def test_synthesis_marks_revenue_not_entered():
    payload = server.financials_for_synthesis(
        {
            "cash_entered": True,
            "cash_value": 100000,
            "mrr_known": False,
            "mrr_value": None,
            "burn_known": True,
            "burn_value": 5000,
            "runway_months": 20.0,
            "runway_no_burn": False,
            "currency": "usd",
        }
    )
    assert "revenue_not_entered" in payload["unknown_fields"]
    assert payload["mrr"] is None


def test_compute_financials_cache_hit_skips_second_db_read():
    server._FINANCIALS_CACHE.clear()
    entries = [
        {
            "type": "revenue",
            "category": "Subscriptions",
            "amount": 1000,
            "month": "2026-09",
            "recurring": True,
        },
    ]
    mock_db = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(
        return_value={"financial_settings": {"cash": 50000, "currency": "usd"}},
    )
    find_mock = MagicMock(return_value=_entries_cursor(entries))
    mock_db.financial_entries.find = find_mock
    with patch.object(server, "db", mock_db):
        first = asyncio.run(server.compute_financials("ws_cache"))
        second = asyncio.run(server.compute_financials("ws_cache"))
    assert first["mrr_known"] is True
    assert second["mrr"] == first["mrr"]
    assert find_mock.call_count == 1


def test_invalidate_financials_cache_forces_recompute():
    server._FINANCIALS_CACHE.clear()
    entries = [
        {
            "type": "expense",
            "category": "Cloud",
            "amount": 100,
            "month": "2026-09",
            "recurring": True,
        },
    ]
    mock_db = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(
        return_value={"financial_settings": {"cash": 1000, "currency": "usd"}},
    )
    find_mock = MagicMock(return_value=_entries_cursor(entries))
    mock_db.financial_entries.find = find_mock
    with patch.object(server, "db", mock_db):
        asyncio.run(server.compute_financials("ws_inv"))
        server.invalidate_financials_cache("ws_inv")
        asyncio.run(server.compute_financials("ws_inv"))
    assert find_mock.call_count == 2


def test_compute_financials_return_entries_reused_by_live_signals():
    server._FINANCIALS_CACHE.clear()
    entries = [
        {
            "type": "expense",
            "category": "Cloud",
            "amount": 250,
            "month": "2026-09",
            "recurring": True,
        },
    ]
    mock_db = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(
        return_value={"financial_settings": {"cash": 10000, "currency": "usd"}},
    )
    find_mock = MagicMock(return_value=_entries_cursor(entries))
    mock_db.financial_entries.find = find_mock
    mock_db.deals.find = MagicMock(return_value=_entries_cursor([]))

    async def _run():
        with patch.object(server, "db", mock_db), \
             patch.object(server, "get_ws", new=AsyncMock(return_value={
                 "workspace_id": "ws_sig", "tasks": {"items": []}, "people": {"people": []},
             })), \
             patch.object(server, "_recent_updates", new=AsyncMock(return_value=[])), \
             patch.object(server, "_department_signal_inputs", new=AsyncMock(return_value=[])):
            await server._workspace_live_signals("ws_sig")

    asyncio.run(_run())
    # One financial_entries read inside compute_financials — not a second for signals.
    assert find_mock.call_count == 1
