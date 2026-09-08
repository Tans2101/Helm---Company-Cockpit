"""Missing cash/MRR/burn must not be coerced to zero."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_missing_finance")

from money_fmt import entered_cash_amount, parse_optional_amount
import server


def test_parse_optional_amount_keeps_zero():
    assert parse_optional_amount(None) is None
    assert parse_optional_amount("") is None
    assert parse_optional_amount(0) == 0.0
    assert parse_optional_amount(0.0) == 0.0
    assert parse_optional_amount(-12.5) == -12.5


def test_legacy_zero_cash_is_not_entered():
    assert entered_cash_amount({"cash": 0}) is None
    assert entered_cash_amount({"cash": None}) is None
    assert entered_cash_amount({}) is None
    assert entered_cash_amount({"cash": 0, "cash_entered": False}) is None


def test_confirmed_zero_cash_is_entered():
    assert entered_cash_amount({"cash": 0, "cash_entered": True}) == 0.0
    assert entered_cash_amount({"cash": 3100000}) == 3100000.0
    assert entered_cash_amount({"cash": 5000, "cash_entered": True}) == 5000.0


def test_synthesis_payload_nulls_missing_cash():
    fin = {
        "cash_entered": False,
        "cash_value": None,
        "mrr_known": False,
        "mrr_value": None,
        "burn_known": False,
        "burn_value": None,
        "runway_months": None,
        "currency": "usd",
    }
    payload = server.financials_for_synthesis(fin)
    assert payload["cash"] is None
    assert payload["cash_entered"] is False
    assert payload["mrr"] is None
    assert payload["runway_months"] is None
    assert "cash_balance_not_entered" in payload["unknown_fields"]
    assert "out of runway" in payload["instructions_for_missing_data"]
    assert "add a cash balance" in payload["instructions_for_missing_data"]


def test_synthesis_payload_keeps_confirmed_zero():
    fin = {
        "cash_entered": True,
        "cash_value": 0.0,
        "mrr_known": True,
        "mrr_value": 0,
        "burn_known": True,
        "burn_value": 40000,
        "runway_months": 0.0,
        "currency": "usd",
    }
    payload = server.financials_for_synthesis(fin)
    assert payload["cash"] == 0.0
    assert payload["runway_months"] == 0.0
    assert payload["mrr"] == 0
    assert "cash_balance_not_entered" not in payload["unknown_fields"]
