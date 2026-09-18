"""SAP Business One Service Layer — login and A/R + A/P invoice sync.

Maps into the same financial_entries shape as QuickBooks/Xero (`qb_txn_id` key
included) so Decision Engine, Reports, and finance_recurrence treat all three
sources identically.

Credentials are per-workspace (Service Layer URL, CompanyDB, username, password)
— no platform OAuth app required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

PAGE_SIZE = 100
MAX_PAGES = 200  # 20k docs — if hit, return complete=False so last_synced_at is not advanced


class SapB1AuthError(Exception):
    """Login rejected or session expired — user must reconnect."""


class SapB1Error(Exception):
    """Non-auth Service Layer failure."""


def normalize_service_layer_url(url: str) -> str:
    """Return a clean Service Layer base URL ending with /b1s/v1."""
    raw = (url or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Service Layer URL is required")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Service Layer URL must be an http(s) address")
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/b1s/v1"):
        base = f"{parsed.scheme}://{parsed.netloc}{path}"
    elif path.endswith("/b1s"):
        base = f"{parsed.scheme}://{parsed.netloc}{path}/v1"
    elif path:
        base = f"{parsed.scheme}://{parsed.netloc}{path}/b1s/v1"
    else:
        base = f"{parsed.scheme}://{parsed.netloc}/b1s/v1"
    return base


def _session_headers(session_id: str, route_id: Optional[str] = None) -> dict:
    cookie = f"B1SESSION={session_id}"
    if route_id:
        cookie = f"{cookie}; ROUTEID={route_id}"
    return {
        "Cookie": cookie,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _parse_doc_date(doc: dict) -> str:
    raw = str(doc.get("DocDate") or doc.get("TaxDate") or "")[:10]
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _line_category(doc: dict) -> str:
    for line in doc.get("DocumentLines") or []:
        if not isinstance(line, dict):
            continue
        for key in ("AccountCode", "ItemDescription", "ItemCode"):
            val = line.get(key)
            if val:
                return str(val)[:80]
    return ""


def map_sap_document(doc: dict, *, kind: str) -> Optional[dict]:
    """Map an Invoices or PurchaseInvoices document to financial_entries fields.

    kind: \"ar\" (customer invoice → revenue) or \"ap\" (purchase invoice → expense).
    """
    if kind not in ("ar", "ap"):
        return None
    if str(doc.get("Cancelled") or "tNO").upper() in ("TYES", "Y", "TRUE", "1"):
        return None

    date_full = _parse_doc_date(doc)
    month = date_full[:7]
    try:
        amount = round(abs(float(doc.get("DocTotal") or 0)), 2)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    doc_entry = doc.get("DocEntry")
    if doc_entry is None:
        return None
    qb_txn_id = f"sap_b1_{kind}_{doc_entry}_{date_full}"

    card = (doc.get("CardName") or "").strip()
    doc_num = doc.get("DocNum")
    comments = (doc.get("Comments") or "").strip()
    category = _line_category(doc) or ("Sales" if kind == "ar" else "Purchases")
    name = (card or comments or category).strip()[:120]
    extras = [p for p in [f"Doc #{doc_num}" if doc_num is not None else "", comments] if p and p != name]
    note = " · ".join(extras)

    if kind == "ap":
        return {
            "type": "expense",
            "category": category,
            "name": name,
            "amount": amount,
            "month": month,
            "note": note[:500],
            "qb_txn_id": qb_txn_id,
            "recurring": False,
            "_sap_raw_type": "purchase_invoice",
        }

    return {
        "type": "revenue",
        "category": category,
        "name": name,
        "amount": amount,
        "month": month,
        "note": note[:500],
        "qb_txn_id": qb_txn_id,
        "recurring": False,
        "_sap_raw_type": "invoice",
    }


def _since_filter(since: Optional[str]) -> str:
    if not since:
        return ""
    day = since[:10]
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return ""
    return f" and DocDate ge '{day}'"


async def login(
    *,
    service_layer_url: str,
    company_db: str,
    username: str,
    password: str,
) -> dict:
    """Authenticate against Service Layer. Returns session fields to store."""
    base = normalize_service_layer_url(service_layer_url)
    company = (company_db or "").strip()
    user = (username or "").strip()
    if not company or not user or not password:
        raise ValueError("Company database, username, and password are required")

    login_url = urljoin(base.rstrip("/") + "/", "Login")
    async with httpx.AsyncClient(timeout=45.0, verify=True) as hc:
        resp = await hc.post(
            login_url,
            json={"CompanyDB": company, "UserName": user, "Password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
    if resp.status_code in (401, 403):
        raise SapB1AuthError(resp.text[:300] or "SAP Business One login rejected")
    if resp.status_code >= 400:
        raise SapB1Error(f"SAP login failed ({resp.status_code}): {resp.text[:300]}")

    body = resp.json() if resp.content else {}
    session_id = str((body or {}).get("SessionId") or "").strip()
    if not session_id:
        session_id = (resp.cookies.get("B1SESSION") or "").strip()
    if not session_id:
        raise SapB1AuthError("SAP login returned no session")

    route_id = (resp.cookies.get("ROUTEID") or "").strip() or None
    return {
        "service_layer_url": base,
        "company_db": company,
        "username": user,
        "password": password,
        "session_id": session_id,
        "route_id": route_id,
        "session_timeout": (body or {}).get("SessionTimeout"),
        "obtained_at": datetime.now(timezone.utc).isoformat(),
    }


async def logout(creds: dict) -> None:
    base = creds.get("service_layer_url") or ""
    session_id = creds.get("session_id") or ""
    if not base or not session_id:
        return
    url = urljoin(base.rstrip("/") + "/", "Logout")
    try:
        async with httpx.AsyncClient(timeout=15.0) as hc:
            await hc.post(
                url,
                headers=_session_headers(session_id, creds.get("route_id")),
            )
    except Exception:
        pass


async def ensure_session(creds: dict) -> dict:
    """Return credentials with a live session (re-login when needed)."""
    if creds.get("session_id") and creds.get("service_layer_url"):
        ping = urljoin(creds["service_layer_url"].rstrip("/") + "/", "$metadata")
        try:
            async with httpx.AsyncClient(timeout=20.0) as hc:
                resp = await hc.get(
                    ping,
                    headers=_session_headers(creds["session_id"], creds.get("route_id")),
                )
            if resp.status_code == 200:
                return creds
            if resp.status_code not in (401, 403):
                return creds
        except httpx.HTTPError:
            pass
    return await login(
        service_layer_url=creds["service_layer_url"],
        company_db=creds["company_db"],
        username=creds["username"],
        password=creds["password"],
    )


async def _fetch_collection(
    creds: dict,
    collection: str,
    *,
    since: Optional[str] = None,
) -> tuple[list[dict], bool]:
    base = creds["service_layer_url"].rstrip("/") + "/"
    select = "DocEntry,DocNum,DocDate,DocTotal,CardName,Comments,Cancelled,DocumentLines"
    filt = f"Cancelled eq 'tNO'{_since_filter(since)}"
    rows: list[dict] = []
    skip = 0
    for _ in range(MAX_PAGES):
        url = (
            f"{urljoin(base, collection)}"
            f"?$select={select}&$filter={filt}"
            f"&$orderby=DocDate asc&$top={PAGE_SIZE}&$skip={skip}"
        )
        async with httpx.AsyncClient(timeout=60.0) as hc:
            resp = await hc.get(
                url,
                headers=_session_headers(creds["session_id"], creds.get("route_id")),
            )
        if resp.status_code in (401, 403):
            raise SapB1AuthError("SAP session expired")
        if resp.status_code >= 400:
            raise SapB1Error(f"SAP {collection} failed ({resp.status_code}): {resp.text[:300]}")
        payload = resp.json() or {}
        page = payload.get("value") or []
        if not isinstance(page, list):
            return rows, True
        rows.extend(d for d in page if isinstance(d, dict))
        if len(page) < PAGE_SIZE:
            return rows, True
        skip += PAGE_SIZE
    return rows, False


async def fetch_sap_transactions(creds: dict, since: Optional[str] = None) -> tuple[list[dict], bool]:
    """Pull A/R Invoices + A/P PurchaseInvoices and map to financial_entries rows.

    Returns (mapped_rows, complete). Do not advance sap_b1_last_synced_at when complete is False.
    """
    live = await ensure_session(creds)
    ar_docs, ar_ok = await _fetch_collection(live, "Invoices", since=since)
    ap_docs, ap_ok = await _fetch_collection(live, "PurchaseInvoices", since=since)
    out: list[dict] = []
    for doc in ar_docs:
        mapped = map_sap_document(doc, kind="ar")
        if mapped:
            out.append(mapped)
    for doc in ap_docs:
        mapped = map_sap_document(doc, kind="ap")
        if mapped:
            out.append(mapped)
    return out, ar_ok and ap_ok


def public_connection_info(creds: dict | None) -> dict:
    """Safe fields for the Integrations UI (never include password/session)."""
    if not creds:
        return {}
    return {
        "service_layer_url": creds.get("service_layer_url") or "",
        "company_db": creds.get("company_db") or "",
        "username": creds.get("username") or "",
    }
