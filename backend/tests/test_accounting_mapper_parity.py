"""Cross-integration mapper parity — QB / Xero / SAP B1 share one ledger shape."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import accounting_map as amap  # noqa: E402
import finance_recurrence as fr  # noqa: E402
import quickbooks as qb  # noqa: E402
import sap_b1  # noqa: E402
import xero as xr  # noqa: E402


def _shape(row: dict) -> dict:
    """Comparable fields after vendor-specific ids/notes are stripped."""
    return {
        "type": row["type"],
        "category": row["category"],
        "amount": row["amount"],
        "is_credit": bool(row.get("is_credit")),
        "month": row["month"],
        "recurring": bool(row.get("recurring")),
    }


def test_default_uncategorized_constant():
    assert amap.DEFAULT_UNCATEGORIZED == "Other"
    assert amap.fallback_category("") == "Other"
    assert amap.fallback_category(None) == "Other"


def test_refund_and_uncategorized_parity_across_mappers():
    """Same refund + bare category must yield identical type/amount/credit/category."""
    # Expense credit / vendor refund — negative source total, no line category.
    qb_row = qb.map_qb_transaction(
        {
            "Id": "r1",
            "TxnDate": "2026-09-10",
            "TotalAmt": -125.5,
            "EntityRef": {"name": "AWS"},
            "Line": [],
        },
        "purchase",
    )
    xero_row = xr.map_xero_invoice(
        {
            "Type": "ACCPAY",
            "Status": "PAID",
            "InvoiceID": "bill-refund",
            "DateString": "2026-09-10",
            "Total": -125.5,
            "Contact": {"Name": "AWS"},
            "LineItems": [],
        },
    )
    sap_row = sap_b1.map_sap_document(
        {
            "DocEntry": 77,
            "DocDate": "2026-09-10",
            "DocTotal": -125.5,
            "CardName": "AWS",
            "Cancelled": "tNO",
            "DocumentLines": [],
        },
        kind="ap",
    )
    assert xero_row is not None and sap_row is not None
    assert _shape(qb_row) == _shape(xero_row) == _shape(sap_row)
    assert _shape(qb_row) == {
        "type": "expense",
        "category": "Other",
        "amount": 125.5,
        "is_credit": True,
        "month": "2026-09",
        "recurring": False,
    }

    # Positive revenue, still uncategorized → Other (not Sales).
    qb_rev = qb.map_qb_transaction(
        {
            "Id": "i1",
            "TxnDate": "2026-09-11",
            "TotalAmt": 500,
            "CustomerRef": {"name": "Acme"},
            "Line": [],
        },
        "invoice",
    )
    xero_rev = xr.map_xero_invoice(
        {
            "Type": "ACCREC",
            "Status": "AUTHORISED",
            "InvoiceID": "inv-1",
            "DateString": "2026-09-11",
            "Total": 500,
            "Contact": {"Name": "Acme"},
            "LineItems": [],
        },
    )
    sap_rev = sap_b1.map_sap_document(
        {
            "DocEntry": 88,
            "DocDate": "2026-09-11",
            "DocTotal": 500,
            "CardName": "Acme",
            "Cancelled": "tNO",
            "DocumentLines": [],
        },
        kind="ar",
    )
    assert _shape(qb_rev) == _shape(xero_rev) == _shape(sap_rev)
    assert _shape(qb_rev)["category"] == "Other"
    assert _shape(qb_rev)["is_credit"] is False
    assert _shape(qb_rev)["amount"] == 500


def test_credit_reduces_expense_totals_identically():
    """Refunds must lower burn the same way regardless of which mapper produced the row."""
    rows = []
    for mapper_row in (
        qb.map_qb_transaction(
            {"Id": "1", "TxnDate": "2026-09-01", "TotalAmt": -40, "EntityRef": {"name": "V"}, "Line": []},
            "purchase",
        ),
        xr.map_xero_invoice(
            {
                "Type": "ACCPAY",
                "Status": "PAID",
                "InvoiceID": "c1",
                "DateString": "2026-09-01",
                "Total": -40,
                "Contact": {"Name": "V"},
                "LineItems": [],
            },
        ),
        sap_b1.map_sap_document(
            {
                "DocEntry": 3,
                "DocDate": "2026-09-01",
                "DocTotal": -40,
                "CardName": "V",
                "Cancelled": "tNO",
            },
            kind="ap",
        ),
    ):
        rows.append(mapper_row)
    totals = [
        fr.expand_entries_by_month([row], entry_type="expense", horizon_end="2026-09")["2026-09"]
        for row in rows
    ]
    assert totals == [-40.0, -40.0, -40.0]
