"""Ask Helm billing-period quota (separate from AI extracts)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import plan_usage
import plans


def test_paid_plans_have_ask_helm_caps():
    assert plans.ask_helm_monthly_limit("free") == 10
    assert plans.ask_helm_monthly_limit("starter") == 50
    assert plans.ask_helm_monthly_limit("growth") == 200
    assert plans.ask_helm_monthly_limit("business") == 500
    # Separate from extract quotas
    assert plans.ai_extracts_limit("starter") == 30
    assert plans.ai_extracts_limit("growth") == 150
    assert plans.ai_extracts_limit("business") == 500


@pytest.mark.asyncio
async def test_acquire_period_ask_slot_respects_limit():
    coll = MagicMock()
    coll.find_one_and_update = AsyncMock(side_effect=[
        {"count": 1},
        {"count": 2},
        None,  # at cap
    ])
    db = MagicMock()
    db.document_usage_periods = coll

    assert await plan_usage.acquire_period_ask_slot(db, "ws1", "2026-09-01", 2) is True
    assert await plan_usage.acquire_period_ask_slot(db, "ws1", "2026-09-01", 2) is True
    assert await plan_usage.acquire_period_ask_slot(db, "ws1", "2026-09-01", 2) is False
    assert coll.find_one_and_update.await_count == 3


@pytest.mark.asyncio
async def test_get_period_ask_count_defaults_zero():
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    db = MagicMock()
    db.document_usage_periods = coll
    assert await plan_usage.get_period_ask_count(db, "ws1", "2026-09-01") == 0
    coll.find_one = AsyncMock(return_value={"count": 7})
    assert await plan_usage.get_period_ask_count(db, "ws1", "2026-09-01") == 7


@pytest.mark.asyncio
async def test_ask_and_extract_use_distinct_actions():
    """Extract and Ask Helm must not share the same usage counter row."""
    calls = []

    async def _find_one(filt, *a, **k):
        calls.append(dict(filt))
        return {"count": 0}

    coll = MagicMock()
    coll.find_one = AsyncMock(side_effect=_find_one)
    db = MagicMock()
    db.document_usage_periods = coll
    await plan_usage.get_period_extract_count(db, "ws1", "p1")
    await plan_usage.get_period_ask_count(db, "ws1", "p1")
    assert calls[0]["action"] == "extract"
    assert calls[1]["action"] == "ask_helm"
