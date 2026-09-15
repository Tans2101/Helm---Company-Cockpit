"""Financial access: report cards, Ask Helm context, restricted markers."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_financial_access_lockdown")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import ask_context_for_synthesis, _computed_report_cards  # noqa: E402


def _sample_fin():
    return {
        "mrr": "$10K",
        "arr": "$120K",
        "runway_months": 12,
        "burn": "$5K",
        "mrr_value": 10000,
        "burn_value": 5000,
        "cash_entered": True,
        "cash_value": 50000.0,
        "mrr_known": True,
        "burn_known": True,
        "currency": "usd",
    }


def test_computed_report_cards_omit_money_when_no_fin_access():
    fin = _sample_fin()
    with_fin = _computed_report_cards({}, fin, [], [], 3, prior=None, include_financials=True)
    without = _computed_report_cards({}, fin, [], [], 3, prior=None, include_financials=False)
    assert [c["id"] for c in with_fin] == ["auto_fin", "auto_team", "auto_exec"]
    assert [c["id"] for c in without] == ["auto_team", "auto_exec"]
    assert all(c["id"] != "auto_fin" for c in without)
    assert "Money check-in" not in [c["title"] for c in without]


def test_ask_context_restricts_financials_when_not_visible():
    fin = _sample_fin()
    c = {
        "name": "Acme",
        "stage": "Seed",
        "employees": 2,
        "people": {"people": [{"id": "p1"}]},
        "decisions": [{"title": "Hire", "status": "pending"}],
        "telemetry_manual": {"risks": []},
    }
    open_ctx = ask_context_for_synthesis(
        c, fin, deals=[], sales_tracked=True, onboarding_instances=[], hr_tracked=True,
        financials_visible=True,
    )
    assert open_ctx["financials"].get("access") != "restricted"
    assert "mrr" in open_ctx["financials"] or "mrr_value" in open_ctx["financials"] or open_ctx["financials"].get("mrr_known") is not None

    locked = ask_context_for_synthesis(
        c, fin, deals=[], sales_tracked=True, onboarding_instances=[], hr_tracked=True,
        financials_visible=False,
    )
    assert locked["financials"] == {
        "access": "restricted",
        "note": "Financial figures are not shared with this user's role.",
    }
    # Non-financial context unchanged
    assert locked["open_decisions"] == ["Hire"]
    assert locked["people_count"] == 1
    assert locked["pipeline"]["deal_count"] == 0
