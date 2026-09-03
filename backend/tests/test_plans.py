"""Unit tests for pricing catalog — no Mongo required."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plans


def test_normalize_legacy_pro():
    assert plans.normalize_plan("pro") == "business"
    assert plans.normalize_plan("PRO") == "business"
    assert plans.normalize_plan(None) == "free"
    assert plans.normalize_plan("starter") == "starter"


def test_free_has_no_paid_features_when_enforced():
    assert plans.plan_allows("free", plans.FEATURE_ASK_HELM, billing_enforced=True) is False
    assert plans.plan_allows("free", plans.FEATURE_AI_EXTRACT, billing_enforced=True) is False
    assert plans.plan_allows("free", plans.FEATURE_INTEGRATIONS, billing_enforced=True) is False


def test_billing_off_allows_everything():
    assert plans.plan_allows("free", plans.FEATURE_ASK_HELM, billing_enforced=False) is True


def test_starter_limits():
    assert plans.seats_limit("starter") == 3
    assert plans.ai_extracts_limit("starter") == 30
    assert plans.plan_allows("starter", plans.FEATURE_ASK_HELM, billing_enforced=True) is True
    assert plans.plan_allows("starter", plans.FEATURE_ADVANCED_REPORTS, billing_enforced=True) is False


def test_growth_and_business():
    assert plans.seats_limit("growth") == 10
    assert plans.ai_extracts_limit("growth") == 150
    assert plans.plan_allows("growth", plans.FEATURE_ADVANCED_REPORTS, billing_enforced=True) is True
    assert plans.seats_limit("business") is None
    assert plans.ai_extracts_limit("business") == 1000


def test_prices():
    assert plans.PLANS["free"]["price"] == 0
    assert plans.PLANS["starter"]["price"] == 15
    assert plans.PLANS["growth"]["price"] == 39
    assert plans.PLANS["business"]["price"] == 99
    assert plans.TRIAL_DAYS == 7


def test_paddle_price_resolution(monkeypatch):
    monkeypatch.delenv("PADDLE_PRICE_ID_STARTER", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_ID_GROWTH", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_ID_BUSINESS", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_ID", raising=False)
    assert plans.paddle_price_id_for("starter") == ""
    monkeypatch.setenv("PADDLE_PRICE_ID_STARTER", "pri_starter")
    assert plans.paddle_price_id_for("starter") == "pri_starter"
    monkeypatch.setenv("PADDLE_PRICE_ID", "pri_legacy")
    assert plans.paddle_price_id_for("business") == "pri_legacy"
    assert plans.plan_for_paddle_price("pri_starter") == "starter"


def test_public_plan_list_shape():
    rows = plans.public_plan_list()
    assert len(rows) == 4
    assert {r["id"] for r in rows} == {"free", "starter", "growth", "business"}
    free = next(r for r in rows if r["id"] == "free")
    assert free["checkout_available"] is False
