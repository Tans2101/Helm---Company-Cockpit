"""Department stall signals: enabled-dept fetch + detector wiring."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_department_decision_signals")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
import department_report_drafts as drafts  # noqa: E402
import decision_engine as eng  # noqa: E402


class Coll:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection=None):
        matched = [dict(r) for r in self.rows if all(r.get(k) == v for k, v in query.items())]
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=matched)
        return cursor


@pytest.mark.asyncio
async def test_department_signal_inputs_skips_disabled_types():
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    production_rows = [{
        "id": "p_stall",
        "workspace_id": "ws_test",
        "name": "Weld",
        "status": "in_progress",
        "updated_at": old,
    }]
    legal_rows = [{
        "id": "lm_stall",
        "workspace_id": "ws_test",
        "title": "NDA",
        "status": "draft",
        "updated_at": old,
    }]

    mock_db = MagicMock()
    mock_db.production_stages = Coll(production_rows)
    mock_db.legal_matters = Coll(legal_rows)
    mock_db.procurement_requests = Coll([])
    mock_db.maintenance_tickets = Coll([])
    mock_db.hr_onboarding_instances = Coll([])

    async def enabled(_db, workspace_id, dept_type):
        if dept_type == "production":
            return {"department_id": "dept_prod", "type": "production", "enabled": True}
        return None

    with patch.object(server, "db", mock_db), \
         patch.object(server.dept_migrate, "get_enabled_department", side_effect=enabled):
        bundles = await server._department_signal_inputs("ws_test")

    types = [b["spec"]["type"] for b in bundles]
    assert types == ["production"]
    assert bundles[0]["items"][0]["id"] == "p_stall"

    signals = eng.collect_department_signals(bundles, now=now)
    assert len(signals) == 1
    assert signals[0]["related_id"] == "p_stall"
    # Legal was stalled but department not enabled — no legal signal
    assert all(s.get("department_type") != "legal" for s in signals)


def test_dept_specs_cover_all_five_queues():
    types = {s["type"] for s in drafts.DEPT_SPECS}
    assert types == {
        "production",
        "procurement",
        "legal",
        "engineering_maintenance",
        "hr",
    }
