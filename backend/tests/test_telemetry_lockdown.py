"""Telemetry helpers: optional targets + risk suggestions from signals."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_telemetry_lockdown")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import (  # noqa: E402
    _normalize_telemetry_targets,
    _revenue_trend_with_targets,
    _telemetry_risk_suggestions_from_signals,
)


def test_targets_default_off_and_clamp_pct():
    assert _normalize_telemetry_targets(None) == {"enabled": False, "monthly_growth_pct": 0.0}
    assert _normalize_telemetry_targets({"enabled": True, "monthly_growth_pct": 5})["enabled"] is True
    assert _normalize_telemetry_targets({"enabled": True, "monthly_growth_pct": 5})["monthly_growth_pct"] == 5.0
    assert _normalize_telemetry_targets({"enabled": True, "monthly_growth_pct": 99999})["monthly_growth_pct"] == 1000.0
    assert _normalize_telemetry_targets({"enabled": True, "monthly_growth_pct": -200})["monthly_growth_pct"] == -100.0


def test_revenue_trend_omits_target_when_disabled():
    series = [{"month": "Jan", "revenue": 100}, {"month": "Feb", "revenue": 110}]
    out = _revenue_trend_with_targets(series, {"enabled": False, "monthly_growth_pct": 3})
    assert out == [
        {"month": "Jan", "mrr": 100},
        {"month": "Feb", "mrr": 110},
    ]
    assert all("target" not in p for p in out)


def test_revenue_trend_compounds_from_prior_actual():
    series = [
        {"month": "Jan", "revenue": 100},
        {"month": "Feb", "revenue": 120},
        {"month": "Mar", "revenue": 130},
    ]
    out = _revenue_trend_with_targets(series, {"enabled": True, "monthly_growth_pct": 10})
    assert out[0]["target"] == 100  # first month = own actual
    assert out[1]["target"] == round(100 * 1.10)  # prior actual × (1+g)
    assert out[2]["target"] == round(120 * 1.10)
    # Not lockstep with same-month actual * 1.03
    assert out[1]["target"] != round(120 * 1.03)


def test_risk_suggestions_dedupe_by_type_and_cap():
    signals = [
        {"type": "recurring_blocker", "summary": "Ada blocked again"},
        {"type": "recurring_blocker", "summary": "Bob blocked again"},
        {"type": "overdue_work_order", "summary": "WO-1 overdue"},
        {"type": "runway_risk", "summary": "Runway under 6 months"},
        {"type": "stalled_deal", "summary": "should be ignored"},
    ]
    out = _telemetry_risk_suggestions_from_signals(signals, cap=5)
    types = [s["source_signal"] for s in out]
    assert types.count("recurring_blocker") == 1
    assert "stalled_deal" not in types
    assert "runway_risk" in types
    rb = next(s for s in out if s["source_signal"] == "recurring_blocker")
    assert rb["category"] == "People"
    assert "2 teammates" in rb["name"]
