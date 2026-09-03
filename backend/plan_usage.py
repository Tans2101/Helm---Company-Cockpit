"""Document upload usage keyed by billing anniversary period (not calendar month)."""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            raw = value.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _parse_dt(value: Any) -> Optional[datetime]:
    return parse_dt(value)


def _safe_month_day(year: int, month: int, day: int) -> datetime:
    last = monthrange(year, month)[1]
    return datetime(year, month, min(day, last), tzinfo=timezone.utc)


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = (dt.month - 1) + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    return _safe_month_day(year, month, dt.day)


def billing_anchor(ws: dict | None) -> Optional[datetime]:
    """Prefer Paddle/subscription start; fall back to workspace created_at."""
    ws = ws or {}
    return (
        _parse_dt(ws.get("billing_period_start"))
        or _parse_dt(ws.get("subscription_started_at"))
        or _parse_dt(ws.get("created_at"))
    )


def current_usage_period(ws: dict | None = None, now: datetime | None = None) -> dict:
    """
    Return the active usage period for a workspace.

    Paid workspaces reset on the billing anniversary day derived from
    subscription start (or workspace creation). Free / unknown anchors use
    calendar month as a fallback.
    """
    now = now or datetime.now(timezone.utc)
    anchor = billing_anchor(ws)
    if not anchor:
        start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        return {
            "key": start.strftime("%Y-%m"),
            "start": start,
            "end": end,
        }

    anchor = anchor.astimezone(timezone.utc)
    # Find latest anniversary <= now
    candidate = _safe_month_day(now.year, now.month, anchor.day)
    if candidate > now:
        # previous month
        if now.month == 1:
            candidate = _safe_month_day(now.year - 1, 12, anchor.day)
        else:
            candidate = _safe_month_day(now.year, now.month - 1, anchor.day)
    # Walk back if still after now (shouldn't happen) or walk forward from far past
    # Ensure we're not before anchor's first period
    if candidate < _safe_month_day(anchor.year, anchor.month, anchor.day):
        candidate = _safe_month_day(anchor.year, anchor.month, anchor.day)

    # If candidate is still more than ~1 month behind, jump near now
    while _add_months(candidate, 1) <= now:
        candidate = _add_months(candidate, 1)

    start = candidate
    end = _add_months(start, 1)
    return {
        "key": start.date().isoformat(),
        "start": start,
        "end": end,
    }


async def get_period_extract_count(db, workspace_id: str, period_key: str) -> int:
    doc = await db.document_usage_periods.find_one(
        {"workspace_id": workspace_id, "period": period_key, "action": "extract"},
        {"_id": 0, "count": 1},
    )
    return int((doc or {}).get("count") or 0)


async def increment_period_extract(db, workspace_id: str, period_key: str) -> int:
    await db.document_usage_periods.update_one(
        {"workspace_id": workspace_id, "period": period_key, "action": "extract"},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=True,
    )
    return await get_period_extract_count(db, workspace_id, period_key)


# Back-compat aliases used by older call sites
async def get_monthly_extract_count(db, workspace_id: str, month: str | None = None, ws: dict | None = None) -> int:
    period = current_usage_period(ws)
    key = month or period["key"]
    return await get_period_extract_count(db, workspace_id, key)


async def increment_monthly_extract(db, workspace_id: str, month: str | None = None, ws: dict | None = None) -> int:
    period = current_usage_period(ws)
    key = month or period["key"]
    return await increment_period_extract(db, workspace_id, key)
