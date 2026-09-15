"""Unit tests for Telemetry activity heatmap aggregation."""
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_activity_heatmap")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import _activity_heatmap_for_workspace  # noqa: E402


@pytest.mark.asyncio
async def test_activity_heatmap_empty_workspace():
    cursor = MagicMock()
    cursor.__aiter__ = lambda self: self
    cursor.__anext__ = AsyncMock(side_effect=StopAsyncIteration)

    with patch("server.db") as mock_db:
        mock_db.activities.find.return_value = cursor
        out = await _activity_heatmap_for_workspace("ws_empty", weeks=12)

    assert out["total"] == 0
    assert len(out["columns"]) == 12
    assert all(len(col["bins"]) == 7 for col in out["columns"])
    assert all(bin_["count"] == 0 for col in out["columns"] for bin_ in col["bins"])


@pytest.mark.asyncio
async def test_activity_heatmap_groups_by_day_with_raw_counts():
    today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    docs = [
        {"created_at": today.isoformat()},
        {"created_at": today.isoformat()},
        {"created_at": yesterday.isoformat()},
    ]

    async def _aiter(self):
        for d in docs:
            yield d

    cursor = MagicMock()
    cursor.__aiter__ = _aiter

    with patch("server.db") as mock_db:
        mock_db.activities.find.return_value = cursor
        out = await _activity_heatmap_for_workspace("ws_busy", weeks=4)

    assert out["total"] == 3
    assert len(out["columns"]) == 4
    by_date = {
        bin_["date"]: bin_["count"]
        for col in out["columns"]
        for bin_ in col["bins"]
    }
    assert by_date[today.date().isoformat()] == 2
    assert by_date[yesterday.date().isoformat()] == 1
    # Future days in the current week stay at 0
    tomorrow = (today + timedelta(days=1)).date()
    if tomorrow.isoformat() in by_date:
        assert by_date[tomorrow.isoformat()] == 0
