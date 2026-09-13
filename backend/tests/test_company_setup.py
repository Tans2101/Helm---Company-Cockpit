"""Company profile setup uses operational maturity, not funding rounds."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_company_setup")

import seed_data  # noqa: E402
import server  # noqa: E402


_FUNDING = ("Pre-seed", "Seed", "Series A", "Series B", "Bootstrapped")


def test_new_workspace_is_not_prefilled_as_series_a():
    empty = seed_data.build_workspace("ws_new", "Acme Metals", "user_1", empty=True)
    assert empty["stage"] == ""
    assert empty["founded"] == ""
    assert empty["industry"] == ""
    for term in _FUNDING:
        assert empty["stage"] != term


def test_sample_workspace_uses_operational_maturity():
    sample = seed_data.build_workspace("ws_sample", "Northwind", "user_1", empty=False)
    assert sample["stage"] in server.COMPANY_STAGES
    for term in _FUNDING:
        assert sample["stage"] != term


def test_company_stages_have_no_funding_rounds():
    for term in _FUNDING:
        assert term not in server.COMPANY_STAGES
    assert "Just starting out" in server.COMPANY_STAGES
    assert "Family-owned / multi-generation" in server.COMPANY_STAGES
