"""Unit tests for recurring expense expansion (monthly / annual)."""
from datetime import datetime

import finance_recurrence as fr


def test_normalize_recurrence():
    assert fr.normalize_recurrence(False, "monthly", "expense") is None
    assert fr.normalize_recurrence(True, "annual", "expense") == "annual"
    assert fr.normalize_recurrence(True, None, "expense") == "monthly"
    assert fr.normalize_recurrence(True, "weekly", "expense") == "monthly"
    assert fr.normalize_recurrence(True, "annual", "revenue") == "monthly"


def test_months_inclusive():
    assert fr.months_inclusive("2026-01", "2026-03") == ["2026-01", "2026-02", "2026-03"]
    assert fr.months_inclusive("2026-03", "2026-01") == []


def test_monthly_expense_expands_each_month():
    entry = {
        "type": "expense",
        "amount": 1000,
        "month": "2026-01",
        "recurring": True,
        "recurrence": "monthly",
        "category": "Cloud/Infra",
    }
    amounts = dict(fr.iter_expense_month_amounts(entry, "2026-03"))
    assert amounts == {"2026-01": 1000, "2026-02": 1000, "2026-03": 1000}


def test_annual_expense_is_monthlyized():
    entry = {
        "type": "expense",
        "amount": 12000,
        "month": "2026-01",
        "recurring": True,
        "recurrence": "annual",
        "category": "G&A",
    }
    amounts = dict(fr.iter_expense_month_amounts(entry, "2026-03"))
    assert amounts == {"2026-01": 1000.0, "2026-02": 1000.0, "2026-03": 1000.0}


def test_one_time_expense_only_start_month():
    entry = {
        "type": "expense",
        "amount": 500,
        "month": "2026-02",
        "recurring": False,
        "category": "Other",
    }
    amounts = dict(fr.iter_expense_month_amounts(entry, "2026-03"))
    assert amounts == {"2026-02": 500}


def test_expense_totals_by_month_category_expands(monkeypatch):
    import decision_engine as eng

    monkeypatch.setattr(fr, "current_month", lambda now=None: "2026-03")
    entries = [
        {
            "type": "expense",
            "amount": 1200,
            "month": "2026-01",
            "recurring": True,
            "recurrence": "monthly",
            "category": "Payroll",
        }
    ]
    out = eng.expense_totals_by_month_category(entries)
    assert out["2026-01"]["Payroll"] == 1200
    assert out["2026-02"]["Payroll"] == 1200
    assert out["2026-03"]["Payroll"] == 1200
