"""Cursor-based pagination helpers for list endpoints."""
from typing import Any, Optional


def clamp_limit(limit: int, *, default: int = 50, maximum: int = 200) -> int:
    if limit <= 0:
        return default
    return min(limit, maximum)


def apply_before_filter(
    base_filter: dict[str, Any],
    sort_field: str,
    before: Optional[str],
) -> dict[str, Any]:
    filt = dict(base_filter)
    if before:
        filt[sort_field] = {"$lt": before}
    return filt


def next_cursor(items: list[dict], sort_field: str, limit: int) -> Optional[str]:
    if len(items) < limit:
        return None
    return items[-1].get(sort_field)
