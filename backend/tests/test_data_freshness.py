"""Unit tests for data freshness / staleness helpers."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DB_NAME", "test_data_freshness")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

import data_freshness as fresh
import departments_catalog as dept_catalog


def test_is_possibly_stale_respects_threshold():
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    fresh_row = {"updated_at": (now - timedelta(days=3)).isoformat()}
    stale_row = {"updated_at": (now - timedelta(days=20)).isoformat()}
    assert fresh.is_possibly_stale(fresh_row, dept_type=dept_catalog.TYPE_PRODUCTION, now=now) is False
    assert fresh.is_possibly_stale(stale_row, dept_type=dept_catalog.TYPE_PRODUCTION, now=now) is True


def test_annotate_possibly_stale():
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    rows = [
        {"id": "a", "updated_at": (now - timedelta(days=1)).isoformat()},
        {"id": "b", "updated_at": (now - timedelta(days=40)).isoformat()},
    ]
    out = fresh.annotate_possibly_stale(rows, dept_type=dept_catalog.TYPE_SALES, now=now)
    assert out[0]["possibly_stale"] is False
    assert out[1]["possibly_stale"] is True
    assert "possibly_stale" not in rows[0]
    assert fresh.count_possibly_stale(out) == 1


def test_pick_data_as_of_takes_latest():
    older = "2026-09-01T12:00:00+00:00"
    newer = "2026-09-10T12:00:00+00:00"
    assert fresh.pick_data_as_of(older, None, newer).startswith("2026-09-10")
    assert fresh.pick_data_as_of(None, "", None) is None


def test_stale_thresholds_are_centralized():
    assert fresh.stale_after_days(dept_catalog.TYPE_PRODUCTION) == 14
    assert fresh.stale_after_days(dept_catalog.TYPE_LEGAL) == 21
    assert fresh.stale_after_days(dept_catalog.TYPE_ACCOUNTING_FINANCE) == 30
    assert fresh.stale_after_days("unknown") == fresh.DEFAULT_STALE_AFTER_DAYS


def test_workspace_source_timestamps():
    ws = {
        "qb_last_synced_at": "2026-09-15T10:00:00+00:00",
        "xero_last_synced_at": None,
    }
    sources = fresh.workspace_source_timestamps(ws)
    assert sources["qb_last_synced_at"].startswith("2026-09-15")
    assert sources["xero_last_synced_at"] is None


def test_ask_and_weekly_pack_prompts_require_literal_grounding():
    import server

    assert "literally" in server._WEEKLY_PACK_SYSTEM
    assert "possibly_stale" in server._WEEKLY_PACK_SYSTEM
    ctx = server.ask_context_for_synthesis(
        {"name": "Acme", "people": {"people": []}, "decisions": [], "telemetry_manual": {}},
        {},
        financials_visible=False,
        sales_enabled=False,
        sales_visible=False,
        hr_enabled=False,
        hr_visible=False,
        production_enabled=True,
        production_visible=True,
        production_rows=[
            {"id": "wo", "status": "in_production", "updated_at": "2000-01-01T00:00:00+00:00"},
        ],
    )
    assert ctx["production"]["possibly_stale_count"] >= 1
    assert "outdated" in (ctx["production"].get("instructions_for_missing_data") or "")
