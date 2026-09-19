"""Procurement spend rollups + optional department budget.

Only priced requests contribute to actual spend. Unpriced requests are counted
separately so the UI can flag incomplete totals. Missing budget → budget_entered
false — never a fabricated gap or percentage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _parse_iso_dt(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def in_period(req: dict, period_start: datetime, period_end: datetime) -> bool:
    """Attribute spend to the period via created_at (updated_at only if missing)."""
    dt = _parse_iso_dt(req.get("created_at")) or _parse_iso_dt(req.get("updated_at"))
    if dt is None:
        return False
    return period_start <= dt < period_end


def spend_rollup(
    requests: list[dict],
    *,
    period_start: datetime,
    period_end: datetime,
    budget: Any = None,
    budget_entered: bool = False,
) -> dict:
    priced: list[dict] = []
    unpriced = 0
    for r in requests:
        if not in_period(r, period_start, period_end):
            continue
        if r.get("cost") is None or r.get("cost") == "":
            unpriced += 1
            continue
        try:
            cost = float(r["cost"])
        except (TypeError, ValueError):
            unpriced += 1
            continue
        priced.append({**r, "_cost": cost})

    actual = round(sum(p["_cost"] for p in priced), 2)
    by_vendor: dict[str, dict] = {}
    by_item: dict[str, dict] = {}
    for p in priced:
        vendor = (p.get("vendor_name") or "").strip() or "(no vendor)"
        item = (p.get("item") or "").strip() or "(no item)"
        v = by_vendor.setdefault(vendor, {"vendor_name": vendor, "total": 0.0, "count": 0})
        v["total"] = round(v["total"] + p["_cost"], 2)
        v["count"] += 1
        i = by_item.setdefault(item, {"item": item, "total": 0.0, "count": 0})
        i["total"] = round(i["total"] + p["_cost"], 2)
        i["count"] += 1

    out = {
        "actual": actual,
        "priced_count": len(priced),
        "unpriced_count": unpriced,
        "by_vendor": sorted(by_vendor.values(), key=lambda x: -x["total"]),
        "by_item": sorted(by_item.values(), key=lambda x: -x["total"]),
        "budget_entered": False,
        "budget": None,
        "gap": None,
        "period": period_start.strftime("%Y-%m"),
        "period_label": period_start.strftime("%B %Y"),
    }
    if budget_entered and budget is not None:
        try:
            b = float(budget)
        except (TypeError, ValueError):
            return out
        out["budget_entered"] = True
        out["budget"] = round(b, 2)
        out["gap"] = round(actual - b, 2)
    return out
