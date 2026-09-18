"""Xero Accounting — token refresh and invoice/bill sync.

Maps into the same financial_entries shape as QuickBooks (`qb_txn_id` key
included) so Decision Engine, Reports, and finance_recurrence treat both
sources identically.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

XERO_CLIENT_ID = os.environ.get("XERO_CLIENT_ID", "")
XERO_CLIENT_SECRET = os.environ.get("XERO_CLIENT_SECRET", "")

TOKEN_URL = "https://identity.xero.com/connect/token"
AUTH_URL = "https://login.xero.com/identity/connect/authorize"
CONNECTIONS_URL = "https://api.xero.com/connections"
API_BASE = "https://api.xero.com/api.xro/2.0"

# offline_access required for refresh tokens; transactions.read covers invoices/bills.
XERO_SCOPES = "offline_access accounting.transactions.read openid profile email"

_DATE_MS_RE = re.compile(r"/Date\((-?\d+)")


class XeroAuthError(Exception):
    """Refresh token invalid or revoked — user must reconnect."""


def _token_needs_refresh(tokens: dict) -> bool:
    obtained = tokens.get("obtained_at")
    if not obtained:
        return True
    try:
        obtained_dt = datetime.fromisoformat(obtained.replace("Z", "+00:00"))
    except ValueError:
        return True
    expires_in = int(tokens.get("expires_in", 1800))
    return obtained_dt + timedelta(seconds=max(expires_in - 300, 0)) <= datetime.now(timezone.utc)


async def refresh_xero_token(tokens: dict) -> dict:
    """Return valid tokens, refreshing via Xero when the access token is near expiry."""
    if not _token_needs_refresh(tokens):
        return tokens
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise XeroAuthError("Missing refresh token")
    if not XERO_CLIENT_ID or not XERO_CLIENT_SECRET:
        raise XeroAuthError("Xero OAuth is not configured")

    async with httpx.AsyncClient(timeout=30.0) as hc:
        resp = await hc.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(XERO_CLIENT_ID, XERO_CLIENT_SECRET),
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise XeroAuthError(resp.text[:300] or "Token refresh failed")

    updated = {**tokens, **resp.json()}
    updated["obtained_at"] = datetime.now(timezone.utc).isoformat()
    # Preserve org selection across refresh.
    for key in ("tenant_id", "tenant_name", "pending_tenants"):
        if key in tokens and key not in updated:
            updated[key] = tokens[key]
    if tokens.get("tenant_id"):
        updated["tenant_id"] = tokens["tenant_id"]
    if tokens.get("tenant_name"):
        updated["tenant_name"] = tokens["tenant_name"]
    return updated


async def fetch_xero_connections(access_token: str) -> list[dict[str, str]]:
    """List Xero organisations (tenants) the token can access."""
    if not access_token:
        raise XeroAuthError("Missing access token")
    async with httpx.AsyncClient(timeout=30.0) as hc:
        resp = await hc.get(
            CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
    if resp.status_code == 401:
        raise XeroAuthError("Xero access token rejected")
    if resp.status_code != 200:
        raise RuntimeError(f"Xero connections failed ({resp.status_code}): {resp.text[:300]}")
    rows = resp.json() or []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (row.get("tenantType") or "ORGANISATION").upper() not in ("ORGANISATION", "ORGANIZATION"):
            continue
        tid = str(row.get("tenantId") or "").strip()
        if not tid:
            continue
        out.append({
            "tenant_id": tid,
            "tenant_name": str(row.get("tenantName") or "Xero organisation").strip(),
            "connection_id": str(row.get("id") or ""),
        })
    return out


def _parse_xero_date(inv: dict) -> str:
    """Return YYYY-MM-DD from DateString or /Date(ms)/."""
    raw = inv.get("DateString") or ""
    if isinstance(raw, str) and len(raw) >= 10 and raw[4] == "-":
        return raw[:10]
    dated = str(inv.get("Date") or "")
    m = _DATE_MS_RE.search(dated)
    if m:
        try:
            ms = int(m.group(1))
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _line_category(inv: dict) -> str:
    for line in inv.get("LineItems") or []:
        if not isinstance(line, dict):
            continue
        for key in ("AccountCode", "Description", "ItemCode"):
            val = line.get(key)
            if val:
                return str(val)[:80]
    return ""


def _line_description(inv: dict) -> str:
    for line in inv.get("LineItems") or []:
        if not isinstance(line, dict):
            continue
        desc = line.get("Description")
        if desc:
            return str(desc).strip()[:120]
    return ""


def map_xero_invoice(inv: dict) -> Optional[dict]:
    """Map a Xero Invoice (ACCREC/ACCPAY) to financial_entries fields (QB-compatible)."""
    import accounting_map as amap

    status = (inv.get("Status") or "").upper()
    if status in ("DRAFT", "DELETED", "VOIDED"):
        return None
    inv_type = (inv.get("Type") or "").upper()
    if inv_type not in ("ACCREC", "ACCPAY"):
        return None

    date_full = _parse_xero_date(inv)
    month = date_full[:7]
    amount, is_credit = amap.normalize_mapped_amount(inv.get("Total"))
    invoice_id = str(inv.get("InvoiceID") or inv.get("InvoiceNumber") or "")
    if not invoice_id:
        return None
    # Same key as QuickBooks mapping so upsert/index/downstream stay identical.
    qb_txn_id = f"xero_{invoice_id}_{date_full}"

    contact = ((inv.get("Contact") or {}) if isinstance(inv.get("Contact"), dict) else {}).get("Name") or ""
    number = inv.get("InvoiceNumber") or ""
    ref = inv.get("Reference") or ""

    category = amap.fallback_category(_line_category(inv))
    line_desc = _line_description(inv)
    name = (contact or line_desc or number or category).strip()[:120]
    extras = [p for p in [number, ref, line_desc] if p and p != name]
    note = " · ".join(extras)

    if inv_type == "ACCPAY":
        return {
            "type": "expense",
            "category": category,
            "name": name,
            "amount": amount,
            "is_credit": is_credit,
            "month": month,
            "note": note[:500],
            "qb_txn_id": qb_txn_id,
            "recurring": False,
            "_xero_raw_type": "bill",
        }

    return {
        "type": "revenue",
        "category": category,
        "name": name,
        "amount": amount,
        "is_credit": is_credit,
        "month": month,
        "note": note[:500],
        "qb_txn_id": qb_txn_id,
        "recurring": False,
        "_xero_raw_type": "invoice",
    }


def _since_where_clause(since: Optional[str]) -> str:
    if not since:
        return ""
    day = since[:10]
    try:
        dt = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return ""
    return f' AND Date>=DateTime({dt.year},{dt.month},{dt.day})'


async def _fetch_invoices(
    access_token: str,
    tenant_id: str,
    inv_type: str,
    since: Optional[str],
) -> list[dict]:
    where = f'Type=="{inv_type}" AND Status!="DELETED" AND Status!="DRAFT" AND Status!="VOIDED"'
    where += _since_where_clause(since)
    url = f"{API_BASE}/Invoices"
    async with httpx.AsyncClient(timeout=60.0) as hc:
        resp = await hc.get(
            url,
            params={"where": where, "page": 1, "order": "Date ASC"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Xero-tenant-id": tenant_id,
                "Accept": "application/json",
            },
        )
    if resp.status_code == 401:
        raise XeroAuthError("Xero access token rejected")
    if resp.status_code == 403:
        raise XeroAuthError("Xero tenant access denied. Reconnect and pick an organisation")
    if resp.status_code != 200:
        raise RuntimeError(f"Xero Invoices failed ({resp.status_code}): {resp.text[:300]}")
    rows = resp.json().get("Invoices") or []
    return rows if isinstance(rows, list) else []


async def fetch_xero_transactions(
    tokens: dict,
    tenant_id: str,
    since: Optional[str] = None,
) -> list[dict]:
    """Fetch ACCREC invoices and ACCPAY bills; optional since ISO date (date portion)."""
    access_token = tokens.get("access_token")
    if not access_token:
        raise XeroAuthError("Missing access token")
    if not tenant_id:
        raise XeroAuthError("Missing Xero tenant_id")

    invoices = await _fetch_invoices(access_token, tenant_id, "ACCREC", since)
    bills = await _fetch_invoices(access_token, tenant_id, "ACCPAY", since)

    mapped: list[dict] = []
    for inv in invoices + bills:
        row = map_xero_invoice(inv)
        if row:
            mapped.append(row)
    return mapped
