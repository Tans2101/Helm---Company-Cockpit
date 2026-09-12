"""Google Cloud Document AI — Invoice Parser for Helm bill uploads.

Uses a service account on the Helm GCP project (operator credentials),
not the workspace owner's Google login. When unset, callers fall through
to Claude. This is the intended use of the GCP $300 trial credits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("helm.document_ai")

_GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "").strip()
_GCP_LOCATION = (os.environ.get("GCP_DOCUMENT_AI_LOCATION") or "us").strip()
_PROCESSOR_ID = os.environ.get("GCP_DOCUMENT_AI_PROCESSOR_ID", "").strip()
_SA_JSON = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "").strip()
_SA_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def document_ai_configured() -> bool:
    return bool((_SA_JSON or _SA_PATH) and _PROCESSOR_ID and _GCP_PROJECT_ID)


def processor_name() -> str:
    if _PROCESSOR_ID.startswith("projects/"):
        return _PROCESSOR_ID
    loc = _GCP_LOCATION or "us"
    return f"projects/{_GCP_PROJECT_ID}/locations/{loc}/processors/{_PROCESSOR_ID}"


def _service_account_info() -> Optional[dict]:
    if _SA_JSON:
        return json.loads(_SA_JSON)
    if _SA_PATH and os.path.isfile(_SA_PATH):
        with open(_SA_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _access_token() -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = _service_account_info()
    if not info:
        raise RuntimeError("GCP service account is not configured")
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Could not mint Document AI access token")
    return creds.token


def _entity_text(entity: dict) -> str:
    norm = entity.get("normalizedValue") or {}
    if isinstance(norm.get("text"), str) and norm["text"].strip():
        return norm["text"].strip()
    return (entity.get("mentionText") or "").strip()


def _entity_amount(entity: dict) -> Optional[float]:
    norm = entity.get("normalizedValue") or {}
    money = norm.get("moneyValue") or {}
    if money:
        units = float(money.get("units") or 0)
        nanos = float(money.get("nanos") or 0)
        total = units + nanos / 1_000_000_000
        return total if total > 0 else None
    text = _entity_text(entity)
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    if not cleaned:
        return None
    try:
        n = float(cleaned)
    except ValueError:
        return None
    return n if n > 0 else None


def _entity_month(entity: dict) -> Optional[str]:
    norm = entity.get("normalizedValue") or {}
    dt = norm.get("datetimeValue") or {}
    year, month = dt.get("year"), dt.get("month")
    if year and month:
        return f"{int(year):04d}-{int(month):02d}"
    text = _entity_text(entity)
    m = re.search(r"(20\d{2})[-/](\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return None


def map_invoice_document(document: dict) -> dict:
    """Turn a Document AI invoice document into Helm extract fields."""
    entities = document.get("entities") or []
    by_type: dict[str, list[dict]] = {}
    for ent in entities:
        key = (ent.get("type") or "").lower()
        by_type.setdefault(key, []).append(ent)

    def first(type_name: str) -> Optional[dict]:
        items = by_type.get(type_name) or []
        return items[0] if items else None

    amount_ent = first("total_amount") or first("net_amount") or first("amount_due")
    amount = _entity_amount(amount_ent) if amount_ent else None
    if amount is None:
        return {"error": "unparseable_amount", "engine": "document_ai"}

    date_ent = first("invoice_date") or first("due_date") or first("receipt_date")
    month = _entity_month(date_ent) if date_ent else None
    if not month or not _MONTH_RE.match(month):
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        confidence = "low"
    else:
        confidence = "high"

    supplier = _entity_text(first("supplier_name") or {}) if first("supplier_name") else ""
    invoice_id = _entity_text(first("invoice_id") or {}) if first("invoice_id") else ""
    name = (f"{supplier} {invoice_id}".strip() if invoice_id else supplier) or "Invoice"
    note = invoice_id and f"Invoice {invoice_id}" or ""

    return {
        "type": "expense",
        "amount": round(amount, 2),
        "month": month,
        "category": "",
        "name": name[:100],
        "vendor": supplier[:100],
        "note": note[:100],
        "confidence": confidence,
        "engine": "document_ai",
    }


async def extract_invoice(file_bytes: bytes, content_type: str) -> Optional[dict]:
    """Process a bill/receipt. Returns Helm extract dict, or None if not configured / API failed."""
    if not document_ai_configured():
        return None
    if content_type not in ("application/pdf", "image/png", "image/jpeg"):
        return None
    import base64

    loc = _GCP_LOCATION or "us"
    url = f"https://{loc}-documentai.googleapis.com/v1/{processor_name()}:process"
    try:
        token = await asyncio.to_thread(_access_token)
    except Exception:
        logger.exception("Document AI token mint failed")
        return None

    payload = {
        "rawDocument": {
            "content": base64.standard_b64encode(file_bytes).decode("ascii"),
            "mimeType": content_type,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as hc:
            resp = await hc.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
    except Exception:
        logger.exception("Document AI request failed")
        return None
    if resp.status_code != 200:
        logger.warning("Document AI HTTP %s: %s", resp.status_code, resp.text[:400])
        return None
    document = (resp.json() or {}).get("document") or {}
    try:
        return map_invoice_document(document)
    except Exception:
        logger.exception("Document AI map failed")
        return None
