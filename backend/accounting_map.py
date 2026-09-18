"""Shared financial_entries shape for QuickBooks, Xero, and SAP B1 mappers.

Migration choice (2026-09): **going forward only** — no one-shot DB backfill.
QuickBooks is the only integration in production use so far; the next sync
upsert rewrites `amount`/`category`/`is_credit` from the live mapper output,
so previously stored negative QB amounts are corrected when those txns sync
again. Stale rows that never reappear in a sync window stay as-is until
touched; burn/runway already treat signed amounts via `entry_signed_amount`.
"""
from __future__ import annotations

from typing import Any, Optional

# Single fallback for uncategorized line items across all accounting sources.
DEFAULT_UNCATEGORIZED = "Other"


def fallback_category(category: Optional[str]) -> str:
    return (str(category or "").strip() or DEFAULT_UNCATEGORIZED)


def normalize_mapped_amount(raw: Any) -> tuple[float, bool]:
    """Return (non-negative amount, is_credit).

    Credits/refunds (negative source totals) store abs(amount) with is_credit=True
    so burn/MRR subtract rather than depending on a signed amount field.
    """
    try:
        signed = float(raw or 0)
    except (TypeError, ValueError):
        signed = 0.0
    amount = round(abs(signed), 2)
    return amount, signed < 0


def entry_signed_amount(entry: dict[str, Any], amount: Optional[float] = None) -> float:
    """Apply credit/refund polarity for ledger expansion and burn/MRR."""
    base = float(entry.get("amount") or 0) if amount is None else float(amount)
    if entry.get("is_credit") or entry.get("is_refund"):
        return -abs(base)
    # Legacy QB rows may still hold a negative amount until the next sync.
    return base
