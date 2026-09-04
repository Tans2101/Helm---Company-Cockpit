"""Cursor-based pagination helpers for list endpoints.

Uses a composite cursor `timestamp\\x1fid` so rows that share the same sort
timestamp are not skipped between pages.
"""
from typing import Any, Optional

CURSOR_SEP = "\x1f"


def clamp_limit(limit: int, *, default: int = 50, maximum: int = 200) -> int:
    if limit <= 0:
        return default
    return min(limit, maximum)


def encode_cursor(sort_value: Any, item_id: Any) -> Optional[str]:
    if sort_value is None:
        return None
    return f"{sort_value}{CURSOR_SEP}{item_id or ''}"


def decode_cursor(before: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not before:
        return None, None
    if CURSOR_SEP in before:
        ts, iid = before.split(CURSOR_SEP, 1)
        return ts, iid or None
    # Legacy plain-timestamp cursors
    return before, None


def apply_before_filter(
    base_filter: dict[str, Any],
    sort_field: str,
    before: Optional[str],
    *,
    id_field: str = "id",
) -> dict[str, Any]:
    filt = dict(base_filter)
    ts, iid = decode_cursor(before)
    if not ts:
        return filt
    if iid:
        # (sort_field, id) lexicographic: strictly before the cursor pair
        filt["$or"] = [
            {sort_field: {"$lt": ts}},
            {sort_field: ts, id_field: {"$lt": iid}},
        ]
    else:
        filt[sort_field] = {"$lt": ts}
    return filt


def next_cursor(items: list[dict], sort_field: str, limit: int, *, id_field: str = "id") -> Optional[str]:
    if len(items) < limit:
        return None
    last = items[-1]
    return encode_cursor(last.get(sort_field), last.get(id_field) or last.get("activity_id"))
