"""First-party product usage events — Helm's MongoDB only, no third-party trackers."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("helm.product_analytics")

EVENT_DEPARTMENT_ENABLED = "department_enabled"
EVENT_DEPARTMENT_PAGE_VIEWED = "department_page_viewed"
EVENT_ONBOARDING_STEP = "onboarding_step_completed"
EVENT_AI_EXTRACT = "ai_extract_used"
EVENT_ASK_HELM = "ask_helm_used"
EVENT_TRIAL_STARTED = "trial_started"
EVENT_TRIAL_CONVERTED = "trial_converted"
EVENT_SUBSCRIPTION_CANCELLED = "subscription_cancelled"

ONBOARDING_STEPS = ("financials", "people", "invite", "update")


def _sanitize_metadata(metadata: Any) -> dict:
    if not isinstance(metadata, dict):
        return {}
    out = {}
    for i, (key, value) in enumerate(metadata.items()):
        if i >= 16:
            break
        k = str(key)[:64]
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[k] = value if not isinstance(value, str) else value[:240]
        else:
            out[k] = str(value)[:240]
    return out


async def log_event(
    db,
    workspace_id: str | None,
    user_id: str | None,
    event_type: str,
    metadata: dict | None = None,
) -> bool:
    """Insert one product event. Never raises; returns False if the write was skipped."""
    try:
        et = (event_type or "").strip()[:80]
        if not et:
            return False
        doc = {
            "workspace_id": (workspace_id or "").strip() or None,
            "user_id": (user_id or "").strip() or None,
            "event_type": et,
            "metadata": _sanitize_metadata(metadata),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.product_events.insert_one(doc)
        return True
    except Exception:
        logger.exception("product_events insert failed event_type=%s", event_type)
        return False


async def log_event_once(
    db,
    workspace_id: str,
    user_id: str | None,
    event_type: str,
    metadata: dict | None = None,
    *,
    once_key: str,
) -> bool:
    """Log at most one event per workspace for a given once_key (e.g. onboarding step)."""
    try:
        existing = await db.product_events.find_one(
            {
                "workspace_id": workspace_id,
                "event_type": event_type,
                "metadata.once_key": once_key,
            },
            {"_id": 1},
        )
        if existing:
            return False
        meta = dict(metadata or {})
        meta["once_key"] = once_key
        return await log_event(db, workspace_id, user_id, event_type, meta)
    except Exception:
        logger.exception("product_events once-check failed event_type=%s", event_type)
        return False


async def emit_billing_funnel(
    db,
    workspace_id: str | None,
    user_id: str | None,
    prev_status: str | None,
    new_status: str | None,
    plan: str | None = None,
) -> None:
    prev = (prev_status or "").lower()
    new = (new_status or "").lower()
    meta = {"plan": plan} if plan else {}
    if new == "trialing" and prev != "trialing":
        await log_event(db, workspace_id, user_id, EVENT_TRIAL_STARTED, meta)
    if new == "active" and prev == "trialing":
        await log_event(db, workspace_id, user_id, EVENT_TRIAL_CONVERTED, meta)
    if new in ("canceled", "cancelled") and prev not in ("canceled", "cancelled"):
        await log_event(db, workspace_id, user_id, EVENT_SUBSCRIPTION_CANCELLED, meta)


async def _count_by_meta(db, event_type: str, field: str) -> dict[str, int]:
    rows = await db.product_events.aggregate([
        {"$match": {"event_type": event_type}},
        {"$group": {"_id": f"$metadata.{field}", "count": {"$sum": 1}}},
    ]).to_list(100)
    out = {}
    for row in rows:
        key = row.get("_id")
        if key is None or key == "":
            key = "(unknown)"
        out[str(key)] = int(row.get("count") or 0)
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


async def _distinct_workspaces(db, event_type: str) -> int:
    vals = await db.product_events.distinct("workspace_id", {"event_type": event_type})
    return len([v for v in vals if v])


async def _workspaces_per_step(db) -> dict[str, int]:
    rows = await db.product_events.aggregate([
        {"$match": {"event_type": EVENT_ONBOARDING_STEP}},
        {"$group": {"_id": {"step": "$metadata.step", "ws": "$workspace_id"}}},
        {"$group": {"_id": "$_id.step", "workspaces": {"$sum": 1}}},
    ]).to_list(20)
    out = {step: 0 for step in ONBOARDING_STEPS}
    for row in rows:
        step = str(row.get("_id") or "")
        out[step] = int(row.get("workspaces") or 0)
    return out


async def analytics_summary(db) -> dict:
    """Cross-workspace aggregates for the product owner — not a customer feature."""
    total_workspaces = await db.workspaces.count_documents({})
    denom = max(total_workspaces, 1)
    steps = await _workspaces_per_step(db)
    trials = await _distinct_workspaces(db, EVENT_TRIAL_STARTED)
    converted = await _distinct_workspaces(db, EVENT_TRIAL_CONVERTED)
    cancelled = await _distinct_workspaces(db, EVENT_SUBSCRIPTION_CANCELLED)
    return {
        "total_workspaces": total_workspaces,
        "department_enabled_counts": await _count_by_meta(db, EVENT_DEPARTMENT_ENABLED, "department"),
        "department_page_view_counts": await _count_by_meta(db, EVENT_DEPARTMENT_PAGE_VIEWED, "department"),
        "onboarding_step_workspaces": steps,
        "onboarding_step_completion_rates": {
            step: round(count / denom, 4) for step, count in steps.items()
        },
        "ai_extract_used": await db.product_events.count_documents({"event_type": EVENT_AI_EXTRACT}),
        "ask_helm_used": await db.product_events.count_documents({"event_type": EVENT_ASK_HELM}),
        "trial_started_workspaces": trials,
        "trial_converted_workspaces": converted,
        "subscription_cancelled_workspaces": cancelled,
        "trial_to_paid_conversion_rate": round(converted / trials, 4) if trials else 0.0,
    }
