"""Plan caps, Free feature blocks, and billing-period usage — no live Mongo required for catalog tests."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plans
import plan_usage


def test_normalize_legacy_pro_to_starter():
    """Existing paying workspaces (plan=pro) land on Starter — conscious migration."""
    assert plans.normalize_plan("pro") == "starter"
    assert plans.normalize_plan("PRO") == "starter"


def test_member_caps_per_plan():
    assert plans.seats_limit("free") == 1
    assert plans.seats_limit("starter") == 3
    assert plans.seats_limit("growth") == 10
    assert plans.seats_limit("business") == 25


def test_document_caps_per_plan():
    assert plans.ai_extracts_limit("free") == 0
    assert plans.ai_extracts_limit("starter") == 30
    assert plans.ai_extracts_limit("growth") == 150
    assert plans.ai_extracts_limit("business") == 500


def test_free_blocks_paid_features():
    assert plans.plan_allows("free", plans.FEATURE_AI_EXTRACT, billing_enforced=True) is False
    assert plans.plan_allows("free", plans.FEATURE_ASK_HELM, billing_enforced=True) is False
    assert plans.plan_allows("free", plans.FEATURE_INTEGRATIONS, billing_enforced=True) is False
    assert plans.plan_allows("free", plans.FEATURE_ADVANCED_REPORTS, billing_enforced=True) is False


def test_starter_allows_core_paid_features():
    assert plans.plan_allows("starter", plans.FEATURE_AI_EXTRACT, billing_enforced=True) is True
    assert plans.plan_allows("starter", plans.FEATURE_ASK_HELM, billing_enforced=True) is True
    assert plans.plan_allows("starter", plans.FEATURE_INTEGRATIONS, billing_enforced=True) is True
    assert plans.plan_allows("starter", plans.FEATURE_ADVANCED_REPORTS, billing_enforced=True) is False


def test_growth_and_business_features():
    assert plans.plan_allows("growth", plans.FEATURE_ADVANCED_REPORTS, billing_enforced=True) is True
    assert plans.plan_allows("business", plans.FEATURE_PRIORITY_SUPPORT, billing_enforced=True) is True


def test_prices_and_trial():
    assert plans.PLANS["free"]["price"] == 0
    assert plans.PLANS["starter"]["price"] == 15
    assert plans.PLANS["growth"]["price"] == 39
    assert plans.PLANS["business"]["price"] == 99
    assert plans.TRIAL_DAYS == 7
    for pid in ("starter", "growth", "business"):
        assert plans.PLANS[pid]["trial_days"] == 7


def test_upgrade_downgrade_helpers():
    assert plans.is_upgrade("free", "starter") is True
    assert plans.is_downgrade("growth", "starter") is True
    assert plans.is_upgrade("business", "starter") is False


def test_paddle_price_ids_from_env_only(monkeypatch):
    for key in (
        "PADDLE_PRICE_ID_STARTER",
        "PADDLE_PRICE_ID_GROWTH",
        "PADDLE_PRICE_ID_BUSINESS",
        "PADDLE_PRICE_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    assert plans.paddle_price_id_for("starter") == ""
    assert plans.any_paddle_price_configured() is False
    monkeypatch.setenv("PADDLE_PRICE_ID_STARTER", "pri_starter_test")
    monkeypatch.setenv("PADDLE_PRICE_ID_GROWTH", "pri_growth_test")
    monkeypatch.setenv("PADDLE_PRICE_ID_BUSINESS", "pri_business_test")
    assert plans.paddle_price_id_for("starter") == "pri_starter_test"
    assert plans.paddle_price_id_for("growth") == "pri_growth_test"
    assert plans.paddle_price_id_for("business") == "pri_business_test"
    # Legacy single PADDLE_PRICE_ID must NOT silently map to a tier
    monkeypatch.setenv("PADDLE_PRICE_ID", "pri_legacy")
    assert plans.plan_for_paddle_price("pri_legacy") is None
    assert plans.plan_for_paddle_price("pri_starter_test") == "starter"


def test_billing_anniversary_period_resets():
    ws = {"billing_period_start": "2026-01-15T12:00:00+00:00"}
    mid = datetime(2026, 3, 20, tzinfo=timezone.utc)
    period = plan_usage.current_usage_period(ws, now=mid)
    assert period["start"].day == 15
    assert period["start"].month == 3
    assert period["end"].month == 4
    assert period["key"] == "2026-03-15"

    # After anniversary day rolls into next period
    next_day = datetime(2026, 4, 15, 1, tzinfo=timezone.utc)
    period2 = plan_usage.current_usage_period(ws, now=next_day)
    assert period2["key"] == "2026-04-15"
    assert period2["key"] != period["key"]


def test_public_plan_list_shape():
    rows = plans.public_plan_list()
    assert len(rows) == 4
    assert {r["id"] for r in rows} == {"free", "starter", "growth", "business"}
    free = next(r for r in rows if r["id"] == "free")
    assert free["checkout_available"] is False
    biz = next(r for r in rows if r["id"] == "business")
    assert biz["seats"] == 25
    assert biz["ai_extracts_mo"] == 500
