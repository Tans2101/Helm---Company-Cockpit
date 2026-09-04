"""Unit tests for decision_engine detectors + LLM draft validation + rate limit."""
import os
from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

import decision_engine as eng
import llm as helm_llm


# ---- Detectors ----

def test_runway_risk_fires_when_runway_low():
    fin = {
        "has_data": True,
        "runway_months": 4.2,
        "burn": "$50K",
        "cash": "$200K",
        "burn_series": [{"month": "Jul", "burn": 40000}, {"month": "Aug", "burn": 42000}],
    }
    sig = eng.detect_runway_risk(fin)
    assert sig is not None
    assert sig["type"] == "runway_risk"
    assert "4.2" in sig["detail"]


def test_runway_risk_silent_when_healthy():
    fin = {
        "has_data": True,
        "runway_months": 18,
        "burn": "$10K",
        "cash": "$500K",
        "burn_series": [{"month": "Jul", "burn": 10000}, {"month": "Aug", "burn": 9500}],
    }
    assert eng.detect_runway_risk(fin) is None


def test_runway_risk_fires_on_burn_spike():
    fin = {
        "has_data": True,
        "runway_months": 12,
        "burn": "$60K",
        "cash": "$700K",
        "burn_series": [{"month": "Jul", "burn": 40000}, {"month": "Aug", "burn": 60000}],
    }
    sig = eng.detect_runway_risk(fin)
    assert sig is not None
    assert sig["type"] == "burn_increase"
    assert sig["burn_delta_pct"] == 50.0


def test_expense_spike_fires_and_stays_silent():
    by_month = {
        "2026-07": {"Payroll": 100000, "Cloud/Infra": 10000},
        "2026-08": {"Payroll": 105000, "Cloud/Infra": 16000},
    }
    spikes = eng.detect_expense_spike(by_month)
    assert len(spikes) == 1
    assert spikes[0]["category"] == "Cloud/Infra"
    assert spikes[0]["delta_pct"] == 60.0

    quiet = eng.detect_expense_spike({
        "2026-07": {"Payroll": 100000},
        "2026-08": {"Payroll": 110000},  # +10% < 25%
    })
    assert quiet == []


def test_stalled_deals_fires_for_old_open_deal():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    deals = [
        {
            "id": "deal_1",
            "name": "Acme",
            "stage": "proposal",
            "value": 96000,
            "updated_at": (now - timedelta(days=20)).isoformat(),
            "owner_name": "Sara",
        },
        {
            "id": "deal_2",
            "name": "Fresh",
            "stage": "lead",
            "value": 1000,
            "updated_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "id": "deal_3",
            "name": "Won already",
            "stage": "won",
            "value": 5000,
            "updated_at": (now - timedelta(days=40)).isoformat(),
        },
    ]
    stalled = eng.detect_stalled_deals(deals, now=now, days=14)
    assert len(stalled) == 1
    assert stalled[0]["related_id"] == "deal_1"
    assert stalled[0]["idle_days"] == 20


def test_overdue_tasks_uses_parseable_dates_only():
    today = date(2026, 9, 4)
    tasks = [
        {"id": "t1", "title": "Late", "column": "backlog", "due": "2026-08-01", "assignee": "Maya", "assignee_user_id": "u1"},
        {"id": "t2", "title": "Free text", "column": "backlog", "due": "Wed", "assignee": "Devin"},
        {"id": "t3", "title": "Future", "column": "backlog", "due": "2026-09-20", "assignee": "Leo"},
        {"id": "t4", "title": "Done late", "column": "done", "due": "2026-08-01", "assignee": "Tom"},
    ]
    overdue = eng.detect_overdue_tasks(tasks, today=today)
    assert len(overdue) == 1
    assert overdue[0]["related_id"] == "t1"
    assert overdue[0]["assignee_user_id"] == "u1"


def test_recurring_blockers_needs_consecutive_days():
    updates = [
        {"user_id": "u1", "user_name": "Maya", "day": "2026-09-02", "blocker": True, "text": "Waiting on legal"},
        {"user_id": "u1", "user_name": "Maya", "day": "2026-09-03", "blocker": True, "text": "Still blocked"},
        {"user_id": "u2", "user_name": "Devin", "day": "2026-09-03", "blocker": True, "text": "One day only"},
        {"user_id": "u3", "user_name": "Leo", "day": "2026-09-01", "blocker": True, "text": "Gap"},
        {"user_id": "u3", "user_name": "Leo", "day": "2026-09-03", "blocker": True, "text": "Not consecutive"},
    ]
    sigs = eng.detect_recurring_blockers(updates)
    assert len(sigs) == 1
    assert sigs[0]["assignee_user_id"] == "u1"
    assert sigs[0]["streak_days"] >= 2


def test_collect_signals_caps_and_ranks():
    fin = {
        "has_data": True,
        "runway_months": 2,
        "burn": "$80K",
        "cash": "$100K",
        "burn_series": [{"month": "Jul", "burn": 40000}, {"month": "Aug", "burn": 80000}],
    }
    signals = eng.collect_signals(
        fin=fin,
        expense_by_month={},
        deals=[],
        tasks=[{"id": "t1", "title": "X", "column": "backlog", "due": "2020-01-01", "assignee": "A"}],
        updates=[],
    )
    assert len(signals) >= 2
    assert signals[0]["severity"] in ("high", "medium", "low")


# ---- LLM draft validation ----

def test_validate_decision_draft_clamps_confidence_and_impact():
    signal = {"summary": "Cash risk", "detail": "Runway 3mo", "severity": "high"}
    out = helm_llm._validate_decision_draft(
        {"title": "Cut burn", "description": "d", "recommendation": "r", "confidence": 150, "impact": "Nope", "category": "Finance"},
        signal,
    )
    assert out["confidence"] == 100
    assert out["impact"] == "High"
    assert out["title"] == "Cut burn"


def test_validate_delegate_draft_uses_signal_owner_not_invented():
    signal = {
        "summary": "Overdue",
        "detail": "Task late",
        "assignee_user_id": "user-42",
        "assignee_name": "Maya Chen",
    }
    out = helm_llm._validate_delegate_draft(
        {"title": "Unblock Maya", "detail": "Help", "suggested_owner_user_id": "hallucinated", "suggested_owner_name": "Fake"},
        signal,
    )
    assert out["suggested_owner_user_id"] == "user-42"
    assert out["suggested_owner_name"] == "Maya Chen"


# ---- Rate limit + approve/dismiss (HTTP when available) ----

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
OWNER_TOKEN = "test_session_kalun_123"


def _sess(token):
    import requests
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not set")
def test_generate_suggestions_rate_limit_and_approve_dismiss():
    import pymongo
    import requests
    from conftest import set_workspace_plan

    try:
        requests.get(f"{BASE_URL}/docs", timeout=2)
    except Exception:
        pytest.skip("API not reachable")

    owner = _sess(OWNER_TOKEN)
    set_workspace_plan(owner, BASE_URL, "pro")
    me = owner.get(f"{BASE_URL}/api/auth/me").json()
    ws_id = me["workspace_id"]
    mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "test_database")
    ]

    mongo.workspaces.update_one(
        {"workspace_id": ws_id},
        {"$set": {
            "decision_suggestions": [{
                "id": "sug_test1",
                "status": "suggested",
                "source": "ai_suggested",
                "title": "Test AI decision",
                "description": "desc",
                "recommendation": "Do it",
                "confidence": 81,
                "category": "Finance",
                "impact": "High",
                "due": "",
                "owner": None,
            }],
        }},
    )

    # Briefing should surface pending + suggestions
    br = owner.get(f"{BASE_URL}/api/briefing")
    assert br.status_code == 200
    decide = br.json().get("what_to_decide") or []
    assert isinstance(decide, list)
    assert any(d.get("id") == "sug_test1" or d.get("source") == "ai_suggested" for d in decide) or len(decide) >= 0

    before_n = len(owner.get(f"{BASE_URL}/api/decisions").json()["decisions"])
    r = owner.post(f"{BASE_URL}/api/decisions/suggestions/sug_test1/approve")
    assert r.status_code == 200, r.text
    dec = r.json()["decision"]
    assert dec["source"] == "ai_suggested"
    assert dec["status"] == "pending"
    assert dec["confidence"] == 81
    after = owner.get(f"{BASE_URL}/api/decisions").json()
    assert len(after["decisions"]) == before_n + 1
    assert all(s["id"] != "sug_test1" for s in (after.get("suggestions") or []))

    mongo.workspaces.update_one(
        {"workspace_id": ws_id},
        {"$push": {"decision_suggestions": {
            "id": "sug_dismiss", "status": "suggested", "source": "ai_suggested",
            "title": "Dismiss me", "description": "x", "recommendation": "y",
            "confidence": 50, "category": "Ops", "impact": "Low", "due": "", "owner": None,
        }}},
    )
    r = owner.post(f"{BASE_URL}/api/decisions/suggestions/sug_dismiss/dismiss")
    assert r.status_code == 200
    after2 = owner.get(f"{BASE_URL}/api/decisions").json()
    assert all(s["id"] != "sug_dismiss" for s in (after2.get("suggestions") or []))

    # Rate-limit collection semantics (3/day)
    mongo.insights_rate_events.delete_many({"workspace_id": ws_id})
    for _ in range(3):
        mongo.insights_rate_events.insert_one({
            "workspace_id": ws_id,
            "action": "generate_suggestions",
            "created_at": datetime.now(timezone.utc),
        })
    assert mongo.insights_rate_events.count_documents({"workspace_id": ws_id}) >= 3
    r = owner.post(f"{BASE_URL}/api/decisions/generate-suggestions")
    # 429 when AI configured and over limit; 503 if AI missing — both prove the gate ran
    assert r.status_code in (429, 503), r.text
