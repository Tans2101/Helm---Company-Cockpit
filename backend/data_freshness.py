"""Data freshness helpers for AI summaries and department queues.

Staleness is distinct from not-entered / confirmed-zero: a figure can be
confirmed zero and still stale if nothing has updated it in a long time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import departments_catalog as dept_catalog

# Days without an update before a department record is flagged possibly_stale.
# Tunable in one place — do not scatter magic numbers across prompts/UI.
STALE_AFTER_DAYS: dict[str, int] = {
    dept_catalog.TYPE_PRODUCTION: 14,
    dept_catalog.TYPE_PROCUREMENT: 14,
    dept_catalog.TYPE_LEGAL: 21,
    dept_catalog.TYPE_ENGINEERING_MAINTENANCE: 14,
    dept_catalog.TYPE_HR: 14,
    dept_catalog.TYPE_SALES: 14,
    dept_catalog.TYPE_ACCOUNTING_FINANCE: 30,
}
DEFAULT_STALE_AFTER_DAYS = 14

_TS_FIELDS = (
    "updated_at",
    "modified_at",
    "last_updated_at",
    "created_at",
    "uploaded_at",
    "summarized_at",
)


def stale_after_days(dept_type: str | None = None) -> int:
    if dept_type and dept_type in STALE_AFTER_DAYS:
        return STALE_AFTER_DAYS[dept_type]
    return DEFAULT_STALE_AFTER_DAYS


def parse_iso_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def item_timestamp(row: dict | None) -> Optional[datetime]:
    if not row:
        return None
    for key in _TS_FIELDS:
        dt = parse_iso_ts(row.get(key))
        if dt:
            return dt
    return None


def is_possibly_stale(
    row: dict | None,
    *,
    dept_type: str | None = None,
    now: Optional[datetime] = None,
) -> bool:
    """True when the record's last known update is older than the threshold."""
    ts = item_timestamp(row)
    if not ts:
        return False
    now = now or datetime.now(timezone.utc)
    age = now - ts
    return age >= timedelta(days=stale_after_days(dept_type))


def annotate_possibly_stale(
    rows: list[dict],
    *,
    dept_type: str | None = None,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Return shallow copies with possibly_stale set (does not mutate inputs)."""
    now = now or datetime.now(timezone.utc)
    out = []
    for row in rows or []:
        item = dict(row)
        item["possibly_stale"] = is_possibly_stale(item, dept_type=dept_type, now=now)
        out.append(item)
    return out


def _max_ts(*candidates: Optional[datetime]) -> Optional[datetime]:
    present = [c for c in candidates if c is not None]
    return max(present) if present else None


def workspace_source_timestamps(workspace: dict | None) -> dict[str, Optional[str]]:
    """Named source timestamps from the workspace doc (ISO strings or None)."""
    ws = workspace or {}
    keys = (
        "qb_last_synced_at",
        "xero_last_synced_at",
        "hubspot_last_synced_at",
        "sap_b1_last_synced_at",
        "insights_generated_at",
    )
    out: dict[str, Optional[str]] = {}
    for key in keys:
        dt = parse_iso_ts(ws.get(key))
        out[key] = dt.isoformat() if dt else None
    return out


def pick_data_as_of(*raw_values: Any) -> Optional[str]:
    """Latest underlying data timestamp among candidates (not generation time)."""
    latest = _max_ts(*(parse_iso_ts(v) for v in raw_values))
    return latest.isoformat() if latest else None


async def resolve_workspace_data_as_of(db, workspace: dict) -> dict:
    """Build an as-of payload from sync stamps + latest financial entry update."""
    sources = workspace_source_timestamps(workspace)
    latest_entry = None
    try:
        cursor = db.financial_entries.find(
            {"workspace_id": workspace.get("workspace_id")},
            {"_id": 0, "updated_at": 1, "created_at": 1},
        ).sort([("updated_at", -1), ("created_at", -1)]).limit(1)
        rows = await cursor.to_list(1)
        latest_entry = rows[0] if rows else None
    except Exception:
        latest_entry = None
    entry_ts = item_timestamp(latest_entry) if latest_entry else None
    if entry_ts:
        sources["financial_entries_updated_at"] = entry_ts.isoformat()
    else:
        sources["financial_entries_updated_at"] = None

    data_as_of = pick_data_as_of(*sources.values())
    return {
        "data_as_of": data_as_of,
        "sources": {k: v for k, v in sources.items() if v},
    }
