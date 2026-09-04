"""Recurring financial entry helpers — monthly/annual expense expansion for burn/runway."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional


VALID_RECURRENCE = frozenset({"monthly", "annual"})


def normalize_recurrence(
    recurring: bool,
    recurrence: Optional[str],
    entry_type: str,
) -> Optional[str]:
    """Return a cadence string or None. Revenue recurring is always monthly (MRR)."""
    if not recurring:
        return None
    if (entry_type or "").strip().lower() == "revenue":
        return "monthly"
    value = (recurrence or "monthly").strip().lower()
    return value if value in VALID_RECURRENCE else "monthly"


def month_add(month: str, delta: int) -> str:
    """Shift YYYY-MM by delta months."""
    year, mon = map(int, month.split("-"))
    idx = year * 12 + (mon - 1) + delta
    return f"{idx // 12:04d}-{(idx % 12) + 1:02d}"


def months_inclusive(start: str, end: str) -> list[str]:
    """Inclusive month list from start..end (YYYY-MM). Empty if start > end."""
    if not start or not end or start > end:
        return []
    out: list[str] = []
    cur = start
    # Cap runaway loops (e.g. bad data) at 240 months / 20 years
    for _ in range(240):
        out.append(cur)
        if cur >= end:
            break
        cur = month_add(cur, 1)
    return out


def current_month(now: Optional[datetime] = None) -> str:
    dt = now or datetime.utcnow()
    return dt.strftime("%Y-%m")


def expense_monthly_amount(entry: dict[str, Any]) -> float:
    """Monthlyized expense amount used in burn series."""
    amount = float(entry.get("amount") or 0)
    if not entry.get("recurring"):
        return amount
    cadence = normalize_recurrence(True, entry.get("recurrence"), "expense")
    if cadence == "annual":
        return round(amount / 12.0, 2)
    return amount


def iter_expense_month_amounts(
    entry: dict[str, Any],
    horizon_end: str,
) -> Iterable[tuple[str, float]]:
    """Yield (YYYY-MM, amount) contributions for an expense entry through horizon_end.

    - One-time: only the entry's month (if within horizon)
    - Monthly recurring: full amount each month from start..horizon
    - Annual recurring: amount/12 each month from start..horizon
    """
    if (entry.get("type") or "").strip().lower() != "expense":
        return
    start = (entry.get("month") or "").strip()
    if not start:
        return
    amount = float(entry.get("amount") or 0)
    if amount == 0:
        return

    if not entry.get("recurring"):
        if start <= horizon_end:
            yield start, amount
        return

    monthly = expense_monthly_amount(entry)
    for month in months_inclusive(start, horizon_end):
        yield month, monthly


def resolve_expense_horizon(entries: list[dict[str, Any]], now: Optional[datetime] = None) -> str:
    """Latest month to expand recurring expenses through."""
    months = [e.get("month") for e in entries if e.get("month")]
    end = current_month(now)
    if months:
        end = max(end, max(months))
    return end
