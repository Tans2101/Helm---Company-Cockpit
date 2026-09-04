"""Unit tests for Team Workload overdue date parsing (no HTTP required)."""
import os

os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from datetime import date

from server import _parse_task_due_date, _count_overdue_tasks


def test_parse_iso_and_common_formats():
    assert _parse_task_due_date("2026-01-15") == date(2026, 1, 15)
    assert _parse_task_due_date("01/15/2026") == date(2026, 1, 15)
    assert _parse_task_due_date("Jan 15, 2026") == date(2026, 1, 15)


def test_free_text_due_dates_are_not_parseable():
    for raw in ("Wed", "Thu", "This week", "Today", "—", "", None):
        assert _parse_task_due_date(raw) is None


def test_overdue_only_counts_parseable_past_dates():
    today = date(2026, 9, 4)
    items = [
        {"due": "2026-09-01", "column": "backlog"},
        {"due": "Wed", "column": "backlog"},
        {"due": "2026-09-10", "column": "backlog"},
        {"due": "", "column": "backlog"},
    ]
    assert _count_overdue_tasks(items, today) == 1
