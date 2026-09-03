"""Helm pricing tiers — Free / Starter / Growth / Business.

Paddle price IDs are optional env vars so checkout can light up per tier
as you configure Paddle. Entitlements work from workspace.plan alone.
"""
from __future__ import annotations

import os
from typing import Any, Optional

# Canonical plan ids (legacy "pro" is treated as Business).
PLAN_FREE = "free"
PLAN_STARTER = "starter"
PLAN_GROWTH = "growth"
PLAN_BUSINESS = "business"
LEGACY_PRO = "pro"

TRIAL_DAYS = 7

# Feature keys used by require_feature / plan_allows
FEATURE_AI_EXTRACT = "ai_extract"
FEATURE_ASK_HELM = "ask_helm"
FEATURE_AI_BRIEFING = "ai_briefing"
FEATURE_INTEGRATIONS = "integrations"
FEATURE_ADVANCED_REPORTS = "advanced_reports"
FEATURE_TEAM = "team"  # invite beyond solo (still subject to seats)

PLANS: dict[str, dict[str, Any]] = {
    PLAN_FREE: {
        "id": PLAN_FREE,
        "label": "Free",
        "price": 0,
        "for": "Solo founders trying it out",
        "seats": 1,
        "ai_extracts_mo": 0,
        "trial_days": 0,
        "paddle_price_env": None,
        "features": {
            FEATURE_AI_EXTRACT: False,
            FEATURE_ASK_HELM: False,
            FEATURE_AI_BRIEFING: False,
            FEATURE_INTEGRATIONS: False,
            FEATURE_ADVANCED_REPORTS: False,
            FEATURE_TEAM: False,
        },
        "includes": [
            "1 user",
            "Manual financial entries",
            "Dashboard & briefing",
            "No AI document upload",
            "No QuickBooks sync",
        ],
    },
    PLAN_STARTER: {
        "id": PLAN_STARTER,
        "label": "Starter",
        "price": 15,
        "for": "Small businesses",
        "seats": 3,
        "ai_extracts_mo": 30,
        "trial_days": TRIAL_DAYS,
        "paddle_price_env": "PADDLE_PRICE_ID_STARTER",
        "features": {
            FEATURE_AI_EXTRACT: True,
            FEATURE_ASK_HELM: True,
            FEATURE_AI_BRIEFING: True,
            FEATURE_INTEGRATIONS: True,
            FEATURE_ADVANCED_REPORTS: False,
            FEATURE_TEAM: True,
        },
        "includes": [
            "Up to 3 team members",
            "AI document upload (30/mo)",
            "QuickBooks sync",
            "Ask Helm AI",
            "Calendar",
            "7-day free trial",
        ],
    },
    PLAN_GROWTH: {
        "id": PLAN_GROWTH,
        "label": "Growth",
        "price": 39,
        "for": "Growing businesses",
        "seats": 10,
        "ai_extracts_mo": 150,
        "trial_days": TRIAL_DAYS,
        "paddle_price_env": "PADDLE_PRICE_ID_GROWTH",
        "features": {
            FEATURE_AI_EXTRACT: True,
            FEATURE_ASK_HELM: True,
            FEATURE_AI_BRIEFING: True,
            FEATURE_INTEGRATIONS: True,
            FEATURE_ADVANCED_REPORTS: True,
            FEATURE_TEAM: True,
        },
        "includes": [
            "Up to 10 members",
            "150 AI extractions/mo",
            "Priority sync",
            "Advanced reports & CEO Pack",
            "7-day free trial",
        ],
    },
    PLAN_BUSINESS: {
        "id": PLAN_BUSINESS,
        "label": "Business",
        "price": 99,
        "for": "Larger companies",
        "seats": None,  # unlimited
        "ai_extracts_mo": 1000,
        "trial_days": TRIAL_DAYS,
        "paddle_price_env": "PADDLE_PRICE_ID_BUSINESS",
        "features": {
            FEATURE_AI_EXTRACT: True,
            FEATURE_ASK_HELM: True,
            FEATURE_AI_BRIEFING: True,
            FEATURE_INTEGRATIONS: True,
            FEATURE_ADVANCED_REPORTS: True,
            FEATURE_TEAM: True,
        },
        "includes": [
            "Unlimited members",
            "Highest AI extraction cap (1,000/mo)",
            "Priority support",
            "Everything in Growth",
            "7-day free trial",
        ],
    },
}

PAID_PLAN_IDS = (PLAN_STARTER, PLAN_GROWTH, PLAN_BUSINESS)

# Pack permission actions → plan feature (None = available on Free when billing enforced)
ACTION_FEATURES: dict[str, Optional[str]] = {
    "briefing:generate": FEATURE_AI_BRIEFING,
    "ask:use": FEATURE_ASK_HELM,
    "reports:pack": FEATURE_ADVANCED_REPORTS,
    "integrations:manage": FEATURE_INTEGRATIONS,
    "members:invite": FEATURE_TEAM,
    "members:manage": None,
    "decisions:act": None,
    "tasks:create": None,
    "tasks:move": None,
    "updates:write": None,
    "billing:manage": None,
}


def normalize_plan(plan: str | None) -> str:
    """Map legacy/unknown plans to a canonical id."""
    if not plan:
        return PLAN_FREE
    p = str(plan).strip().lower()
    if p == LEGACY_PRO:
        return PLAN_BUSINESS
    if p in PLANS:
        return p
    return PLAN_FREE


def plan_def(plan: str | None) -> dict[str, Any]:
    return PLANS[normalize_plan(plan)]


def is_paid_plan(plan: str | None) -> bool:
    return normalize_plan(plan) in PAID_PLAN_IDS


def plan_allows(plan: str | None, feature: str, *, billing_enforced: bool = True) -> bool:
    """When billing is off, everything is allowed (dev / soft launch)."""
    if not billing_enforced:
        return True
    return bool(plan_def(plan)["features"].get(feature))


def seats_limit(plan: str | None) -> Optional[int]:
    """None means unlimited."""
    return plan_def(plan)["seats"]


def ai_extracts_limit(plan: str | None) -> int:
    return int(plan_def(plan)["ai_extracts_mo"] or 0)


def paddle_price_id_for(plan: str | None) -> str:
    """Resolve Paddle price id from env. Legacy PADDLE_PRICE_ID aliases Business."""
    pid = normalize_plan(plan)
    if pid == PLAN_FREE:
        return ""
    env_key = PLANS[pid].get("paddle_price_env")
    price_id = (os.environ.get(env_key) or "").strip() if env_key else ""
    if price_id:
        return price_id
    # Migration: single legacy price maps to Business (or requested paid tier if only one configured)
    legacy = (os.environ.get("PADDLE_PRICE_ID") or "").strip()
    if legacy and pid == PLAN_BUSINESS:
        return legacy
    return ""


def plan_for_paddle_price(price_id: str | None) -> Optional[str]:
    if not price_id:
        return None
    for pid in PAID_PLAN_IDS:
        if paddle_price_id_for(pid) == price_id:
            return pid
    legacy = (os.environ.get("PADDLE_PRICE_ID") or "").strip()
    if legacy and price_id == legacy:
        return PLAN_BUSINESS
    return None


def any_paddle_price_configured() -> bool:
    return any(paddle_price_id_for(pid) for pid in PAID_PLAN_IDS)


def public_plan_list() -> list[dict[str, Any]]:
    """API-safe catalog for Billing / marketing."""
    out = []
    for pid, p in PLANS.items():
        price_id = paddle_price_id_for(pid) if pid != PLAN_FREE else ""
        out.append({
            "id": pid,
            "label": p["label"],
            "price": p["price"],
            "for": p["for"],
            "seats": p["seats"],
            "ai_extracts_mo": p["ai_extracts_mo"],
            "trial_days": p["trial_days"],
            "includes": list(p["includes"]),
            "features": dict(p["features"]),
            "checkout_available": bool(price_id) if pid != PLAN_FREE else False,
        })
    return out


def feature_for_action(action: str) -> Optional[str]:
    return ACTION_FEATURES.get(action)
