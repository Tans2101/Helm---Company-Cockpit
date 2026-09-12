"""Shared helpers for financial ledger item names (distinct from category)."""
from __future__ import annotations

from typing import Any

MAX_ENTRY_NAME_LEN = 120


def normalize_entry_name(name: Any, category: Any) -> str:
    """Always return a non-empty line-item label.

    Prefer an explicit name. If missing/blank, use category so legacy rows never
    render as empty (distinct from a human setting a generic label).
    """
    raw = str(name or "").strip()
    if raw:
        return raw[:MAX_ENTRY_NAME_LEN]
    cat = str(category or "").strip() or "Other"
    return cat[:MAX_ENTRY_NAME_LEN]


def require_entry_name(name: Any) -> str:
    """Manual create/edit: a specific item name is required."""
    raw = str(name or "").strip()
    if not raw:
        raise ValueError("name is required")
    return raw[:MAX_ENTRY_NAME_LEN]
