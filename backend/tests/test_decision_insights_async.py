"""In-process tests for insights generation, rate limit, and briefing wiring."""
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pymongo

os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture
def mongo():
    return pymongo.MongoClient(MONGO_URL)[DB_NAME]


@pytest.mark.asyncio
async def test_generate_insights_rate_limit_and_writes_suggestions(mongo):
    import rate_limit as rl
    import llm as helm_llm
    from server import _generate_insights, db as server_db

    ws_id = f"ws_insights_{uuid.uuid4().hex[:8]}"
    mongo.workspaces.delete_many({"workspace_id": ws_id})
    mongo.insights_rate_events.delete_many({"workspace_id": ws_id})
    mongo.financial_entries.delete_many({"workspace_id": ws_id})
    mongo.deals.delete_many({"workspace_id": ws_id})
    mongo.updates.delete_many({"workspace_id": ws_id})

    mongo.workspaces.insert_one({
        "workspace_id": ws_id,
        "name": "Insights Co",
        "plan": "pro",
        "stage": "Seed",
        "employees": 5,
        "tasks": {"items": [
            {"id": "t1", "title": "Overdue report", "column": "backlog", "due": "2020-01-01",
             "assignee": "Maya", "assignee_user_id": "u_maya"},
        ], "columns": []},
        "decisions": [],
        "people": {"people": []},
        "decision_suggestions": [],
        "delegate_suggestions": [],
        "financial_settings": {"cash": 40000, "gross_margin": 70, "currency": "usd"},
        "briefing": {"what_to_decide": [], "what_to_delegate": [], "what_changed": []},
    })
    # Expense spike data (unique qb_txn_id avoids sparse unique index collisions on null)
    mongo.financial_entries.insert_many([
        {"id": "e1", "workspace_id": ws_id, "type": "expense", "category": "Cloud/Infra",
         "amount": 10000, "month": "2026-07", "recurring": True, "qb_txn_id": f"qb_{uuid.uuid4().hex[:8]}"},
        {"id": "e2", "workspace_id": ws_id, "type": "expense", "category": "Cloud/Infra",
         "amount": 16000, "month": "2026-08", "recurring": True, "qb_txn_id": f"qb_{uuid.uuid4().hex[:8]}"},
        {"id": "e3", "workspace_id": ws_id, "type": "revenue", "category": "Subscriptions",
         "amount": 5000, "month": "2026-08", "recurring": True, "qb_txn_id": f"qb_{uuid.uuid4().hex[:8]}"},
    ])
    # Stalled deal
    mongo.deals.insert_one({
        "id": "deal_stall", "workspace_id": ws_id, "name": "Stalled Acme",
        "stage": "proposal", "value": 50000,
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        "owner_name": "Sara",
    })
    # Recurring blocker
    today = datetime.now(timezone.utc).date()
    mongo.updates.insert_many([
        {"workspace_id": ws_id, "user_id": "u_maya", "user_name": "Maya",
         "day": (today - timedelta(days=1)).isoformat(), "blocker": True, "text": "Blocked A"},
        {"workspace_id": ws_id, "user_id": "u_maya", "user_name": "Maya",
         "day": today.isoformat(), "blocker": True, "text": "Blocked B"},
    ])

    async def fake_decision(signal, ctx):
        return {
            "title": f"Decide:{signal['type']}",
            "description": signal.get("detail") or "",
            "recommendation": "Act.",
            "confidence": 72,
            "category": "Finance",
            "impact": "High",
        }

    async def fake_delegate(signal, ctx):
        return {
            "title": f"Delegate:{signal['type']}",
            "detail": signal.get("detail") or "",
            "suggested_owner_user_id": signal.get("assignee_user_id"),
            "suggested_owner_name": signal.get("assignee_name") or "Someone",
        }

    with patch.object(helm_llm, "anthropic_configured", return_value=True), \
         patch.object(helm_llm, "draft_decision", new=AsyncMock(side_effect=fake_decision)), \
         patch.object(helm_llm, "draft_delegate", new=AsyncMock(side_effect=fake_delegate)):
        result = await _generate_insights(ws_id, raise_on_rate_limit=True)

    assert result.get("ok") is True
    assert result["signals"] >= 1
    ws = mongo.workspaces.find_one({"workspace_id": ws_id})
    assert ws.get("insights_generated_at")
    assert isinstance(ws.get("decision_suggestions"), list)
    assert isinstance(ws.get("delegate_suggestions"), list)
    # At least one of decision or delegate suggestions from our seeded signals
    assert len(ws["decision_suggestions"]) + len(ws["delegate_suggestions"]) >= 1

    # Rate limit: fill to cap then expect 429
    from fastapi import HTTPException
    mongo.insights_rate_events.delete_many({"workspace_id": ws_id})
    for _ in range(rl.INSIGHTS_DAILY_LIMIT):
        await rl.record_insights_event(server_db, ws_id)
    with pytest.raises(HTTPException) as ei:
        await _generate_insights(ws_id, raise_on_rate_limit=True)
    assert ei.value.status_code == 429

    # Soft skip when raise_on_rate_limit=False (briefing lazy path)
    skipped = await _generate_insights(ws_id, raise_on_rate_limit=False)
    assert skipped.get("skipped") == "rate_limited"

    # Cleanup
    mongo.workspaces.delete_many({"workspace_id": ws_id})
    mongo.insights_rate_events.delete_many({"workspace_id": ws_id})
    mongo.financial_entries.delete_many({"workspace_id": ws_id})
    mongo.deals.delete_many({"workspace_id": ws_id})
    mongo.updates.delete_many({"workspace_id": ws_id})


@pytest.mark.asyncio
async def test_briefing_builders_use_live_decisions_and_suggestions():
    from server import _briefing_what_to_decide, _briefing_what_to_delegate

    c = {
        "decisions": [
            {"id": "d1", "title": "Manual hire", "status": "pending", "impact": "High",
             "recommendation": "Hire now", "description": "", "due": "2026-09-10", "source": "manual"},
            {"id": "d2", "title": "Resolved", "status": "approved", "impact": "High"},
        ],
        "decision_suggestions": [
            {"id": "sug1", "title": "AI runway call", "status": "suggested", "impact": "High",
             "recommendation": "Cut burn", "confidence": 80, "source": "ai_suggested"},
        ],
        "delegate_suggestions": [
            {"id": "del1", "title": "Unblock Maya", "detail": "Help", "status": "suggested",
             "suggested_owner_name": "Maya", "suggested_owner_user_id": "u1"},
        ],
    }
    decide = _briefing_what_to_decide(c)
    assert len(decide) == 2
    sources = {x["source"] for x in decide}
    assert "manual" in sources and "ai_suggested" in sources
    assert all(x.get("urgency") for x in decide)

    delegate = _briefing_what_to_delegate(c)
    assert len(delegate) == 1
    assert delegate[0]["owner"] == "Maya"
    assert delegate[0]["id"] == "del1"
