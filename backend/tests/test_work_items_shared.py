"""Shared work_items helpers + People workload batching."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_work_items_shared")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import work_items as wi  # noqa: E402


def _cursor(rows):
    c = MagicMock()
    c.to_list = AsyncMock(return_value=list(rows))
    return c


@pytest.mark.asyncio
async def test_workload_counts_batched_and_overdue():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    mock_db = MagicMock()

    def depts_find(query, projection=None):
        dtype = query.get("type")
        if dtype == "production":
            return _cursor([{"department_id": "d_prod"}])
        if dtype == "legal":
            return _cursor([{"department_id": "d_legal"}])
        return _cursor([])

    mock_db.departments.find = MagicMock(side_effect=depts_find)
    mock_db.production_work_orders.find = MagicMock(return_value=_cursor([
        {
            "assigned_user_ids": ["u_a", "u_b"],
            "due_date": yesterday,
            "status": "in_production",
        },
        {
            "assigned_user_ids": ["u_a"],
            "due_date": tomorrow,
            "status": "in_production",
        },
    ]))
    mock_db.legal_matters.find = MagicMock(return_value=_cursor([
        {"assigned_to": "u_b", "due_date": yesterday, "status": "draft"},
    ]))
    mock_db.maintenance_tickets.find = MagicMock(return_value=_cursor([]))
    mock_db.hr_onboarding_instances.find = MagicMock(return_value=_cursor([]))
    mock_db.hr_offboarding_instances.find = MagicMock(return_value=_cursor([]))
    mock_db.deals.find = MagicMock(return_value=_cursor([]))

    out = await wi.workload_counts_by_user(mock_db, "ws1", ["u_a", "u_b", "u_c"])
    assert out["u_a"]["open_item_count"] == 2
    assert out["u_a"]["overdue_item_count"] == 1
    assert out["u_b"]["open_item_count"] == 2  # shared WO + legal
    assert out["u_b"]["overdue_item_count"] == 2
    assert out["u_c"]["open_item_count"] == 0
    # One departments.find per type that is checked (prod, legal, maint, hr, sales)
    assert mock_db.departments.find.call_count == 5
    mock_db.production_work_orders.find.assert_called_once()
    mock_db.legal_matters.find.assert_called_once()


@pytest.mark.asyncio
async def test_collect_for_user_respects_dept_scope():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    mock_db = MagicMock()
    mock_db.production_work_orders.find = MagicMock(return_value=_cursor([
        {
            "id": "wo1",
            "reference": "WO-1",
            "assigned_user_ids": ["u_me"],
            "status": "in_production",
            "due_date": tomorrow,
        },
    ]))
    mock_db.legal_matters.find = MagicMock(return_value=_cursor([]))
    mock_db.maintenance_tickets.find = MagicMock(return_value=_cursor([]))
    mock_db.hr_onboarding_instances.find = MagicMock(return_value=_cursor([]))
    mock_db.hr_offboarding_instances.find = MagicMock(return_value=_cursor([]))
    mock_db.deals.find = MagicMock(return_value=_cursor([]))
    mock_db.procurement_requests.find = MagicMock(return_value=_cursor([]))

    items = await wi.collect_for_user(
        mock_db,
        "ws1",
        "u_me",
        department_ids_by_type={
            "production": ["d_prod"],
            "legal": None,  # skip
            "engineering_maintenance": None,
            "hr": None,
            "sales": None,
            "procurement": None,
        },
    )
    assert len(items) == 1
    assert items[0]["title"] == "WO-1"
    mock_db.legal_matters.find.assert_not_called()
