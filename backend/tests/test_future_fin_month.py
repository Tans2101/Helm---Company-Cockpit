"""Future-dated financial months must not redefine burn/MRR/runway horizon."""
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_future_fin_month")

import finance_recurrence as fr  # noqa: E402
import server  # noqa: E402


NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_horizon_capped_at_current_month():
    entries = [
        {"month": "2026-08", "type": "expense", "amount": 100},
        {"month": "2027-01", "type": "expense", "amount": 99999},
    ]
    assert fr.resolve_expense_horizon(entries, NOW) == "2026-09"
    assert fr.resolve_expense_horizon(entries, NOW, allow_future=True) == "2027-01"


def test_partition_splits_scheduled():
    current, scheduled = fr.partition_ledger_entries(
        [
            {"id": "a", "month": "2026-08"},
            {"id": "b", "month": "2027-01"},
            {"id": "c", "month": "bad"},
        ],
        NOW,
    )
    assert [e["id"] for e in current] == ["a"]
    assert [e["id"] for e in scheduled] == ["b"]


def test_future_one_time_does_not_enter_expansion():
    entries = [
        {"id": "past", "type": "expense", "amount": 1000, "month": "2026-09",
         "recurring": False, "category": "Ops"},
        {"id": "future", "type": "expense", "amount": 50000, "month": "2027-01",
         "recurring": False, "category": "Ops"},
    ]
    current, scheduled = fr.partition_ledger_entries(entries, NOW)
    horizon = fr.resolve_expense_horizon(current, NOW)
    by = fr.expand_entries_by_month(current, entry_type="expense", horizon_end=horizon)
    assert by.get("2026-09") == 1000
    assert "2027-01" not in by
    assert len(scheduled) == 1


def _entries_cursor(rows):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows)
    return cursor


def test_compute_financials_ignores_future_for_latest_month():
    import simple_cache
    simple_cache.clear()
    rows = [
        {
            "type": "expense",
            "category": "Ops",
            "amount": 3000,
            "month": "2026-09",
            "recurring": True,
        },
        {
            "type": "expense",
            "category": "Scheduled",
            "amount": 90000,
            "month": "2027-01",
            "recurring": False,
            "id": "fe_future",
            "source": "quickbooks_sync",
            "name": "Future invoice",
        },
    ]
    mock_db = MagicMock()
    mock_db.workspaces.find_one = AsyncMock(
        return_value={"financial_settings": {"cash": 30000, "currency": "usd", "cash_entered": True}},
    )
    mock_db.financial_entries.find = MagicMock(return_value=_entries_cursor(rows))
    with patch.object(server, "db", mock_db), patch.object(
        fr, "current_month", lambda now=None: "2026-09",
    ):
        fin = asyncio.run(server.compute_financials("ws_future", bypass_cache=True))
    assert fin["latest_month"] == "2026-09"
    assert fin["horizon_month"] == "2026-09"
    assert fin["scheduled_count"] == 1
    assert fin["scheduled_entries"][0]["month"] == "2027-01"
    # Burn should reflect Sept expense, not the 2027 spike
    assert fin["burn_known"] is True
    assert fin["burn_value"] == 3000


def test_manual_entry_rejects_future_month():
    payload = server.FinEntryInput(
        type="expense",
        category="Ops",
        name="Typo year",
        amount=100,
        month="2027-01",
    )
    principal = {
        "user_id": "u1",
        "workspace_id": "ws1",
        "email": "a@b.c",
        "name": "A",
        "role": "owner",
        "pack": "owner",
    }
    with patch.object(fr, "current_month", lambda now=None: "2026-09"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(server.add_fin_entry(payload, principal))
    assert exc.value.status_code == 400
    assert "future" in str(exc.value.detail).lower()
