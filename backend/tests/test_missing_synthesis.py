"""Missing-vs-entered discipline for AI synthesis payloads (non-finance helpers)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_missing_synthesis")

import server


def test_calendar_not_connected_is_unknown_not_free_day():
    payload = server.calendar_for_synthesis(None)
    assert payload["connected"] is False
    assert payload["meetings"] is None
    assert payload["meeting_count"] is None
    assert "calendar" in payload["unknown_fields"]
    assert "not connected" in payload["instructions_for_missing_data"]
    assert "free day" in payload["instructions_for_missing_data"]


def test_calendar_connected_empty_is_confirmed_zero():
    payload = server.calendar_for_synthesis({"meetings": []})
    assert payload["connected"] is True
    assert payload["meetings"] == []
    assert payload["meeting_count"] == 0
    assert payload["unknown_fields"] == []


def test_pipeline_not_tracked_is_unknown_not_zero():
    payload = server.pipeline_for_synthesis([], sales_tracked=False)
    assert payload["tracked"] is False
    assert payload["deal_count"] is None
    assert payload["open_value"] is None
    assert "sales_pipeline" in payload["unknown_fields"]
    assert "not available" in payload["instructions_for_missing_data"]


def test_pipeline_tracked_empty_is_confirmed_zero():
    payload = server.pipeline_for_synthesis([], sales_tracked=True)
    assert payload["tracked"] is True
    assert payload["deal_count"] == 0
    assert payload["open_value"] == 0
    assert payload["unknown_fields"] == []


def test_onboarding_not_tracked_is_unknown_not_zero():
    payload = server.onboarding_for_synthesis([], hr_tracked=False)
    assert payload["tracked"] is False
    assert payload["instance_count"] is None
    assert "hr_onboarding" in payload["unknown_fields"]
    assert "not available" in payload["instructions_for_missing_data"]


def test_onboarding_tracked_empty_is_confirmed_zero():
    payload = server.onboarding_for_synthesis([], hr_tracked=True)
    assert payload["tracked"] is True
    assert payload["instance_count"] == 0
    assert payload["unknown_fields"] == []


def test_risks_sample_is_unknown_not_empty_radar():
    payload = server.risks_for_synthesis({"telemetry": {"risks": [{"label": "Sample"}]}})
    assert payload["tracked"] is False
    assert payload["items"] is None
    assert "risk_radar" in payload["unknown_fields"]


def test_risks_manual_empty_is_confirmed_zero():
    payload = server.risks_for_synthesis({"telemetry_manual": {"risks": []}})
    assert payload["tracked"] is True
    assert payload["items"] == []
    assert payload["unknown_fields"] == []


def test_company_profile_default_zero_employees_is_unknown():
    payload = server.company_profile_for_synthesis({"name": "Acme", "stage": "", "employees": 0})
    assert payload["stage"] is None
    assert payload["employees"] is None
    assert "employees" in payload["unknown_fields"]
    assert "stage" in payload["unknown_fields"]


def test_company_profile_confirmed_zero_employees_is_preserved():
    payload = server.company_profile_for_synthesis({
        "name": "Acme",
        "stage": "Seed",
        "employees": 0,
        "employees_entered": True,
    })
    assert payload["stage"] == "Seed"
    assert payload["employees"] == 0
    assert payload["unknown_fields"] == []


def test_decision_context_nulls_missing_cash():
    fin = {
        "cash_entered": False,
        "cash_value": None,
        "mrr_known": False,
        "mrr_value": None,
        "burn_known": False,
        "burn_value": None,
        "runway_months": None,
        "currency": "usd",
    }
    payload = server.company_context_for_synthesis({"name": "Acme", "employees": 0}, fin)
    assert payload["cash"] is None
    assert payload["cash_entered"] is False
    assert "cash_balance_not_entered" in payload["unknown_fields"]
    assert "out of runway" in payload["instructions_for_missing_data"]


def test_decision_context_keeps_confirmed_zero_cash():
    fin = {
        "cash_entered": True,
        "cash_value": 0.0,
        "mrr_known": True,
        "mrr_value": 0,
        "burn_known": True,
        "burn_value": 40000,
        "runway_months": 0.0,
        "currency": "usd",
    }
    payload = server.company_context_for_synthesis(
        {"name": "Acme", "stage": "Seed", "employees": 3}, fin,
    )
    assert payload["cash"] == 0.0
    assert payload["mrr"] == 0
    assert payload["runway_months"] == 0.0
    assert "cash_balance_not_entered" not in payload["unknown_fields"]


def test_ask_context_does_not_treat_untracked_pipeline_as_zero():
    fin = {
        "cash_entered": False,
        "cash_value": None,
        "mrr_known": False,
        "mrr_value": None,
        "burn_known": False,
        "burn_value": None,
        "runway_months": None,
        "currency": "usd",
    }
    c = {
        "name": "Acme",
        "stage": "",
        "employees": 0,
        "decisions": [],
        "telemetry": {"kpis": [{"label": "Sample MRR", "value": "$0"}], "risks": [{"label": "Fake"}]},
    }
    payload = server.ask_context_for_synthesis(
        c, fin, deals=[], sales_tracked=False, onboarding_instances=[], hr_tracked=False,
    )
    assert "kpis" not in payload
    assert payload["pipeline"]["deal_count"] is None
    assert payload["onboarding"]["instance_count"] is None
    assert payload["risks"]["items"] is None
    assert payload["open_decisions"] == []


def test_ask_context_preserves_confirmed_empty_pipeline_and_onboarding():
    fin = {
        "cash_entered": True,
        "cash_value": 0.0,
        "mrr_known": True,
        "mrr_value": 0,
        "burn_known": True,
        "burn_value": 0,
        "runway_months": 0.0,
        "currency": "usd",
    }
    c = {
        "name": "Acme",
        "stage": "Seed",
        "employees": 2,
        "decisions": [{"title": "Hire", "status": "pending"}],
        "telemetry_manual": {"risks": []},
    }
    payload = server.ask_context_for_synthesis(
        c, fin, deals=[], sales_tracked=True, onboarding_instances=[], hr_tracked=True,
    )
    assert payload["pipeline"]["deal_count"] == 0
    assert payload["pipeline"]["open_value"] == 0
    assert payload["onboarding"]["instance_count"] == 0
    assert payload["risks"]["items"] == []
    assert payload["financials"]["cash"] == 0.0
    assert payload["open_decisions"] == ["Hire"]
