"""Procurement sourcing / fulfillment lead-time metrics.

Missing timestamps are "not tracked" — never treated as zero delay.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
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


def _parse_date(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if "T" in s:
            s = s.split("T", 1)[0]
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_between(a: datetime | date, b: datetime | date) -> float:
    """Signed day difference: b − a (positive when b is later)."""
    if isinstance(a, datetime):
        a_d = a.astimezone(timezone.utc).date()
    else:
        a_d = a
    if isinstance(b, datetime):
        b_d = b.astimezone(timezone.utc).date()
    else:
        b_d = b
    return float((b_d - a_d).days)


def lead_time_metrics(req: dict) -> dict:
    """Per-request lead-time fields. Absent timestamps → tracked: false / nulls."""
    created = _parse_iso_dt(req.get("created_at"))
    vendor_at = _parse_iso_dt(req.get("vendor_selected_at"))
    ordered_at = _parse_iso_dt(req.get("ordered_at"))
    expected = _parse_date(req.get("expected_delivery_date"))
    actual = _parse_date(req.get("actual_delivery_date"))

    sourcing_days = None
    sourcing_tracked = False
    if created and vendor_at:
        sourcing_days = round(_days_between(created, vendor_at), 1)
        sourcing_tracked = True

    fulfillment_days = None
    fulfillment_tracked = False
    if ordered_at and actual:
        fulfillment_days = round(_days_between(ordered_at, actual), 1)
        fulfillment_tracked = True

    fulfillment_delay_days = None
    delay_tracked = False
    if expected and actual:
        fulfillment_delay_days = round(_days_between(expected, actual), 1)
        delay_tracked = True

    return {
        "sourcing_days": sourcing_days,
        "sourcing_tracked": sourcing_tracked,
        "fulfillment_days": fulfillment_days,
        "fulfillment_tracked": fulfillment_tracked,
        "fulfillment_delay_days": fulfillment_delay_days,
        "delay_tracked": delay_tracked,
    }


def attach_lead_time_metrics(req: dict) -> dict:
    out = dict(req)
    out["lead_time"] = lead_time_metrics(req)
    return out


def is_currently_late(req: dict, *, today: Optional[date] = None) -> bool:
    """Ordered (not delivered) with expected date in the past."""
    if (req.get("status") or "") != "ordered":
        return False
    if req.get("actual_delivery_date"):
        return False
    expected = _parse_date(req.get("expected_delivery_date"))
    if not expected:
        return False
    today = today or datetime.now(timezone.utc).date()
    return expected < today


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def vendor_performance(history: list[dict]) -> dict:
    """Aggregate fulfillment metrics for one vendor's past requests.

    Only rows with tracked timestamps contribute — unknowns are excluded,
    never averaged as zero.
    """
    delays: list[float] = []
    fulfillments: list[float] = []
    for row in history:
        m = lead_time_metrics(row)
        if m["delay_tracked"] and m["fulfillment_delay_days"] is not None:
            delays.append(float(m["fulfillment_delay_days"]))
        if m["fulfillment_tracked"] and m["fulfillment_days"] is not None:
            fulfillments.append(float(m["fulfillment_days"]))
    return {
        "avg_fulfillment_delay_days": _mean(delays),
        "avg_fulfillment_days": _mean(fulfillments),
        "delay_sample_count": len(delays),
        "fulfillment_sample_count": len(fulfillments),
    }


def department_lead_time_summary(requests: list[dict], *, today: Optional[date] = None) -> dict:
    """Rollup for Procurement list / Briefing — never averages unknowns as zero."""
    today = today or datetime.now(timezone.utc).date()
    sourcing: list[float] = []
    delays: list[float] = []
    late: list[dict] = []
    for req in requests:
        m = lead_time_metrics(req)
        if m["sourcing_tracked"] and m["sourcing_days"] is not None:
            sourcing.append(float(m["sourcing_days"]))
        if m["delay_tracked"] and m["fulfillment_delay_days"] is not None:
            delays.append(float(m["fulfillment_delay_days"]))
        if is_currently_late(req, today=today):
            late.append({
                "id": req.get("id"),
                "item": req.get("item") or "",
                "vendor_name": req.get("vendor_name") or "",
                "expected_delivery_date": req.get("expected_delivery_date") or "",
                "priority": req.get("priority") or "normal",
            })
    return {
        "avg_sourcing_days": _mean(sourcing),
        "sourcing_sample_count": len(sourcing),
        "avg_fulfillment_delay_days": _mean(delays),
        "delay_sample_count": len(delays),
        "currently_late_count": len(late),
        "currently_late": late[:20],
    }
