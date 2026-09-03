"""Monthly AI document extraction usage (plan quotas), separate from hourly abuse limits."""
from __future__ import annotations

from datetime import datetime, timezone


def current_month_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


async def get_monthly_extract_count(db, workspace_id: str, month: str | None = None) -> int:
    month = month or current_month_key()
    doc = await db.document_usage_monthly.find_one(
        {"workspace_id": workspace_id, "month": month, "action": "extract"},
        {"_id": 0, "count": 1},
    )
    return int((doc or {}).get("count") or 0)


async def increment_monthly_extract(db, workspace_id: str, month: str | None = None) -> int:
    month = month or current_month_key()
    await db.document_usage_monthly.update_one(
        {"workspace_id": workspace_id, "month": month, "action": "extract"},
        {"$inc": {"count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return await get_monthly_extract_count(db, workspace_id, month)
