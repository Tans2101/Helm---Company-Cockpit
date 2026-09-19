"""Unit tests for procurement lead-time and production daily-log helpers."""
from datetime import date

import procurement_metrics as pm
import production_daily_logs as pdl


def test_sourcing_not_tracked_without_vendor_timestamp():
    m = pm.lead_time_metrics({
        "created_at": "2026-09-01T10:00:00+00:00",
        "vendor_name": "Acme",
    })
    assert m["sourcing_tracked"] is False
    assert m["sourcing_days"] is None


def test_sourcing_and_fulfillment_delay():
    m = pm.lead_time_metrics({
        "created_at": "2026-09-01T10:00:00+00:00",
        "vendor_selected_at": "2026-09-04T12:00:00+00:00",
        "ordered_at": "2026-09-05T09:00:00+00:00",
        "expected_delivery_date": "2026-09-10",
        "actual_delivery_date": "2026-09-12",
    })
    assert m["sourcing_tracked"] is True
    assert m["sourcing_days"] == 3.0
    assert m["fulfillment_tracked"] is True
    assert m["fulfillment_days"] == 7.0
    assert m["delay_tracked"] is True
    assert m["fulfillment_delay_days"] == 2.0


def test_summary_excludes_untracked_from_averages():
    rows = [
        {
            "id": "a",
            "status": "delivered",
            "created_at": "2026-09-01T00:00:00+00:00",
            "vendor_selected_at": "2026-09-03T00:00:00+00:00",
            "ordered_at": "2026-09-03T00:00:00+00:00",
            "expected_delivery_date": "2026-09-08",
            "actual_delivery_date": "2026-09-10",
        },
        {
            "id": "b",
            "status": "approved",  # not yet ordered — not currently late
            "created_at": "2026-09-01T00:00:00+00:00",
            "expected_delivery_date": "2026-09-05",
            # no timestamps — must not pull average toward 0
        },
        {
            "id": "c",
            "status": "ordered",
            "item": "Late bolts",
            "vendor_name": "SlowCo",
            "expected_delivery_date": "2026-09-01",
            "created_at": "2026-08-20T00:00:00+00:00",
        },
    ]
    summary = pm.department_lead_time_summary(rows, today=date(2026, 9, 10))
    assert summary["sourcing_sample_count"] == 1
    assert summary["avg_sourcing_days"] == 2.0
    assert summary["delay_sample_count"] == 1
    assert summary["avg_fulfillment_delay_days"] == 2.0
    assert summary["currently_late_count"] == 1
    assert summary["currently_late"][0]["id"] == "c"


def test_vendor_performance_skips_unknowns():
    hist = [
        {
            "ordered_at": "2026-09-01T00:00:00+00:00",
            "actual_delivery_date": "2026-09-05",
            "expected_delivery_date": "2026-09-04",
        },
        {"created_at": "2026-08-01T00:00:00+00:00"},  # no delivery timestamps
    ]
    perf = pm.vendor_performance(hist)
    assert perf["delay_sample_count"] == 1
    assert perf["avg_fulfillment_delay_days"] == 1.0
    assert perf["fulfillment_sample_count"] == 1
    assert perf["avg_fulfillment_days"] == 4.0


def test_daily_log_no_fabricated_zero_completion():
    e = pdl.enrich_daily_log({"date": "2026-09-10"})
    assert e["target_logged"] is False
    assert e["actual_logged"] is False
    assert e["target_completion_pct"] is None


def test_work_order_rollup_independent_and_empty():
    empty = pdl.rollup_work_order_logs([], quantity_planned=100)
    assert empty["has_logs"] is False
    assert empty["vs_planned_pct"] is None

    logs_a = [
        {"date": "2026-09-01", "target_quantity": 10, "actual_quantity": 8},
        {"date": "2026-09-02", "target_quantity": 10, "actual_quantity": 12},
    ]
    logs_b = [
        {"date": "2026-09-01", "target_quantity": 50, "actual_quantity": 40},
    ]
    a = pdl.rollup_work_order_logs(logs_a, quantity_planned=100)
    b = pdl.rollup_work_order_logs(logs_b, quantity_planned=200)
    assert a["cumulative_target"] == 20
    assert a["cumulative_actual"] == 20
    assert b["cumulative_target"] == 50
    assert b["cumulative_actual"] == 40
    assert a["cumulative_target"] != b["cumulative_target"]


def test_yield_optional_and_unit_mismatch():
    same = pdl.enrich_daily_log({
        "actual_quantity": 80,
        "input_quantity": 100,
        "unit": "kg",
        "input_unit": "kg",
        "expected_yield_pct": 90,
    })
    assert same["actual_yield_pct"] == 80.0
    assert same["yield_below_benchmark"] is True

    mismatch = pdl.enrich_daily_log({
        "actual_quantity": 50,
        "input_quantity": 100,
        "unit": "liters",
        "input_unit": "kg",
    })
    assert mismatch["actual_yield_pct"] is None
    assert mismatch["yield_comparable"] is False
    assert mismatch["yield_raw"]["output_unit"] == "liters"


def test_overtime_cost():
    e = pdl.enrich_daily_log({
        "overtime_hours": 2.5,
        "overtime_rate_per_hour": 20,
        "actual_quantity": 10,
        "target_quantity": 12,
    })
    assert e["overtime_cost"] == 50.0
    assert e["shortfall"] == 2.0


def test_department_day_summary_missing_logs():
    wos = [
        {"id": "w1", "status": "in_production", "unit": "kg"},
        {"id": "w2", "status": "in_production", "unit": "kg"},
        {"id": "w3", "status": "completed", "unit": "kg"},
    ]
    logs = {
        "w1": [{"date": "2026-09-10", "target_quantity": 10, "actual_quantity": 7, "unit": "kg", "overtime_hours": 1, "overtime_rate_per_hour": 15}],
    }
    s = pdl.department_day_summary(wos, logs, day="2026-09-10")
    assert s["active_work_orders"] == 2
    assert s["orders_with_log"] == 1
    assert s["orders_missing_log"] == 1
    assert s["total_target"] == 10
    assert s["total_actual"] == 7
    assert s["unit"] == "kg"
    assert s["mixed_units"] is False
    assert s["overtime_cost"] == 15.0


def test_department_day_summary_mixed_units():
    wos = [
        {"id": "w1", "status": "in_production", "unit": "kg"},
        {"id": "w2", "status": "in_production", "unit": "liters"},
    ]
    logs = {
        "w1": [{"date": "2026-09-10", "target_quantity": 10, "actual_quantity": 8, "unit": "kg"}],
        "w2": [{"date": "2026-09-10", "target_quantity": 100, "actual_quantity": 90, "unit": "liters"}],
    }
    s = pdl.department_day_summary(wos, logs, day="2026-09-10")
    assert s["mixed_units"] is True
    assert s["total_target"] is None
    assert s["total_actual"] is None
    assert len(s["by_unit"]) == 2
    by = {r["unit"]: r for r in s["by_unit"]}
    assert by["kg"]["total_actual"] == 8
    assert by["liters"]["total_actual"] == 90


def test_normalize_unit_required():
    assert pdl.normalize_unit(" kg ", required=True) == "kg"
    try:
        pdl.normalize_unit("", required=True)
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert pdl.normalize_unit(None, required=False) == ""
