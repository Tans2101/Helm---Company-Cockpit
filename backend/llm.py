"""Direct Anthropic API helpers — no Emergent LLM proxy."""
from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or ""
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

_EXTRACT_SYSTEM = """You extract financial data from bills, receipts, and invoices.
Return ONLY strict JSON with no markdown and no prose.

If the document is clearly NOT a bill, receipt, or invoice (e.g. resume, contract, marketing flyer, letter), return:
{"error": "not_financial"}

Otherwise return:
{"type": "revenue"|"expense", "category": string, "amount": number, "month": "YYYY-MM", "vendor": string, "note": string, "confidence": "high"|"medium"|"low"}

Rules:
- type is usually "expense" for bills/invoices you pay; use "revenue" only for incoming invoices you issued.
- amount is the total in USD (number only, no currency symbols).
- month is the invoice/bill date as YYYY-MM when possible; otherwise best estimate.
- category should be a short label like Payroll, Cloud/Infra, Sales & Mktg, G&A, Subscriptions, etc.
- Do not guess amounts or dates — use confidence "low" when uncertain.
"""

_client: Optional[AsyncAnthropic] = None


def anthropic_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def get_client() -> AsyncAnthropic:
    global _client
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


async def complete(system: str, user: str, *, max_tokens: int = 1200) -> str:
    client = get_client()
    msg = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in msg.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


async def stream_text(system: str, user: str, *, max_tokens: int = 1600) -> AsyncIterator[str]:
    client = get_client()
    async with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for text in stream.text_stream:
            if text:
                yield text


def _parse_extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse model response as JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Model response was not a JSON object")
    return data


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_VALID_CONFIDENCE = frozenset({"high", "medium", "low"})
_MAX_LABEL_LEN = 100


def _coerce_label(value) -> str:
    if value is None:
        return ""
    return str(value).strip()[:_MAX_LABEL_LEN]


def _parse_positive_amount(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        return n if n > 0 else None
    cleaned = re.sub(r"[\s$,]", "", str(value).strip())
    if not cleaned:
        return None
    try:
        n = float(cleaned)
    except ValueError:
        return None
    return n if n > 0 else None


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _validate_extracted_financial(data: dict) -> dict:
    """Normalize and validate Claude extraction output for the entry form."""
    if data.get("error"):
        return data

    confidence = data.get("confidence")
    if confidence not in _VALID_CONFIDENCE:
        confidence = "medium"

    type_val = data.get("type")
    if type_val not in ("revenue", "expense"):
        type_val = "expense"
        confidence = "low"

    amount = _parse_positive_amount(data.get("amount"))
    if amount is None:
        return {"error": "unparseable_amount"}

    month = data.get("month")
    if not isinstance(month, str) or not _MONTH_RE.match(month.strip()):
        month = _current_month()
        confidence = "low"
    else:
        month = month.strip()

    return {
        "type": type_val,
        "amount": round(amount, 2),
        "month": month,
        "category": _coerce_label(data.get("category")),
        "vendor": _coerce_label(data.get("vendor")),
        "note": _coerce_label(data.get("note")),
        "confidence": confidence,
    }


async def extract_financial_document(file_bytes: bytes, content_type: str) -> dict:
    if content_type == "application/pdf":
        block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(file_bytes).decode("ascii")},
        }
    elif content_type in ("image/png", "image/jpeg"):
        block = {
            "type": "image",
            "source": {"type": "base64", "media_type": content_type, "data": base64.standard_b64encode(file_bytes).decode("ascii")},
        }
    else:
        raise ValueError(f"Unsupported content type for extraction: {content_type}")

    client = get_client()
    msg = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=_EXTRACT_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                block,
                {"type": "text", "text": "Extract the financial transaction from this document."},
            ],
        }],
    )
    parts = []
    for block_out in msg.content:
        text = getattr(block_out, "text", None)
        if text:
            parts.append(text)
    raw = "".join(parts).strip()
    if not raw:
        raise ValueError("Empty response from model")
    return _validate_extracted_financial(_parse_extract_json(raw))
