"""Unit tests for sales order book, maintenance ops, and procurement spend helpers."""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import maintenance_ops as mo  # noqa: E402
import procurement_spend as ps  # noqa: E402
import sales_order_book as sob  # noqa: E402


def test_order_book_total_and_summary():
    assert sob.compute_total(10, 3) == 30.0
    entries = [
        {
            "status": "confirmed",
            "total_value": 1000,
            "country": "IN",
            "product": "Oil",
            "expected_close_month": "2026-09",
            "created_at": "2026-09-01T00:00:00+00:00",
        },
        {
            "status": "expected",
            "total_value": 500,
            "country": "AE",
            "product": "Oil",
            "expected_close_month": "2026-10",
            "created_at": "2026-09-02T00:00:00+00:00",
        },
        {
            "status": "confirmed",
            "total_value": 200,
            "country": "IN",
            "product": "Meal",
            "created_at": "2026-09-05T00:00:00+00:00",
        },
    ]
    s = sob.order_book_summary(entries, month="2026-09", today=date(2026, 9, 15))
    assert s["confirmed_this_month"] == 1200.0
    assert s["expected_this_month"] == 0.0
    assert s["by_country"][0]["country"] == "IN"
    assert len(s["forward_pipeline"]) == 3
    assert s["forward_pipeline"][1]["month"] == "2026-10"
    assert s["forward_pipeline"][1]["expected"] == 500.0


def test_target_not_set_vs_set():
    bare = sob.target_vs_actual(target_row=None, confirmed_actual=3000)
    assert bare["target_entered"] is False
    assert bare["gap"] is None
    assert bare["pct_of_target"] is None
    assert bare["label"] == "no target set"

    hit = sob.target_vs_actual(target_row={"target": 5000}, confirmed_actual=3000)
    assert hit["target_entered"] is True
    assert hit["gap"] == -2000.0
    assert hit["pct_of_target"] == 60.0


def test_spares_below_threshold():
    rows = [
        {"part_name": "Bearing", "quantity_on_hand": 2, "minimum_threshold": 5},
        {"part_name": "Belt", "quantity_on_hand": 10, "minimum_threshold": 5},
    ]
    below = mo.spares_below_threshold(rows)
    assert len(below) == 1
    assert below[0]["part_name"] == "Bearing"
    assert below[0]["is_below_threshold"] is True


def test_schedule_no_fabricated_due_and_overdue():
    unset = mo.enrich_schedule({"equipment_name": "Press", "frequency_days": 30})
    assert unset["next_due_at"] is None
    assert unset["schedule_established"] is False
    assert unset["is_overdue"] is False

    overdue = mo.enrich_schedule(
        {
            "equipment_name": "Press",
            "frequency_days": 30,
            "last_done_at": "2026-07-01T00:00:00+00:00",
        },
        today=date(2026, 9, 15),
    )
    assert overdue["is_overdue"] is True
    assert overdue["next_due_at"] is not None


def test_contract_flags():
    expired = mo.enrich_contract(
        {"coverage_end": "2026-01-01", "renewal_date": "2026-01-01"},
        today=date(2026, 9, 15),
    )
    assert expired["expired"] is True
    soon = mo.enrich_contract(
        {"coverage_end": "2026-10-01", "renewal_date": "2026-10-01"},
        today=date(2026, 9, 15),
    )
    assert soon["renewal_due_soon"] is True
    assert soon["expired"] is False


def test_overhead_budget_not_entered():
    r = mo.overhead_rollup(
        ticket_costs=[100.0], ledger_costs=[50.0], budget=None, budget_entered=False,
    )
    assert r["actual"] == 150.0
    assert r["budget_entered"] is False
    assert r["gap"] is None

    r2 = mo.overhead_rollup(
        ticket_costs=[1000000], ledger_costs=[], budget=100000, budget_entered=True,
    )
    assert r2["gap"] == 900000.0


def test_procurement_spend_skips_unpriced():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [
        {"item": "Bolts", "vendor_name": "Acme", "cost": 100, "updated_at": "2026-09-10T00:00:00+00:00"},
        {"item": "Nuts", "vendor_name": "Acme", "updated_at": "2026-09-11T00:00:00+00:00"},  # no cost
        {"item": "Oil", "vendor_name": "Other", "cost": 50, "updated_at": "2026-08-01T00:00:00+00:00"},  # out of period
    ]
    s = ps.spend_rollup(rows, period_start=start, period_end=end, budget=None, budget_entered=False)
    assert s["actual"] == 100.0
    assert s["unpriced_count"] == 1
    assert s["budget_entered"] is False
    s2 = ps.spend_rollup(rows, period_start=start, period_end=end, budget=80, budget_entered=True)
    assert s2["gap"] == 20.0
