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
# Default Sonnet model — see current IDs at https://docs.anthropic.com/en/docs/about-claude/models/overview
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

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


_DECISION_DRAFT_SYSTEM = """You are Helm, drafting a decision card for a CEO based on a real signal detected in their business data.
Return ONLY strict JSON with no markdown and no prose:
{"title": string, "description": string, "recommendation": string, "confidence": number, "category": string, "impact": "High"|"Medium"|"Low"}

Rules:
- Be specific — cite the actual numbers, names, and dates from the signal. Do not write generically.
- confidence is your genuine estimate from 0-100 that this recommendation is the right call given the signal (integer).
- category is a short label like Finance, Sales, People, Product, Ops.
- impact reflects business urgency: High / Medium / Low.
"""

_DELEGATE_DRAFT_SYSTEM = """You are Helm, drafting a delegation card for a CEO based on a real operational signal.
Return ONLY strict JSON with no markdown and no prose:
{"title": string, "detail": string, "suggested_owner_user_id": string, "suggested_owner_name": string}

Rules:
- Be specific — cite the task, person, and dates from the signal.
- suggested_owner_user_id and suggested_owner_name MUST come from the signal context (assignee_user_id / assignee_name). Do not invent a person.
- title is a short actionable handoff; detail explains what to do and why.
"""

_VALID_IMPACT = frozenset({"High", "Medium", "Low"})


def _validate_decision_draft(data: dict, signal: dict) -> dict:
    title = _coerce_label(data.get("title"))
    if not title:
        title = _coerce_label(signal.get("summary")) or "Review detected signal"
    description = str(data.get("description") or signal.get("detail") or "").strip()[:800]
    recommendation = str(data.get("recommendation") or "").strip()[:800]
    if not recommendation:
        recommendation = "Review the signal and choose a course of action."

    conf_raw = data.get("confidence")
    try:
        confidence = int(round(float(conf_raw)))
    except (TypeError, ValueError):
        confidence = 60
    confidence = max(0, min(100, confidence))

    impact = data.get("impact")
    if impact not in _VALID_IMPACT:
        sev = (signal.get("severity") or "medium").lower()
        impact = {"high": "High", "medium": "Medium", "low": "Low"}.get(sev, "Medium")

    category = _coerce_label(data.get("category")) or _coerce_label(signal.get("category")) or "General"
    return {
        "title": title[:200],
        "description": description,
        "recommendation": recommendation,
        "confidence": confidence,
        "category": category or "General",
        "impact": impact,
    }


def _validate_delegate_draft(data: dict, signal: dict) -> dict:
    title = _coerce_label(data.get("title"))
    if not title:
        title = _coerce_label(signal.get("summary")) or "Follow up on blocker"
    detail = str(data.get("detail") or signal.get("detail") or "").strip()[:800]
    # Owner must come from the signal — never invent
    owner_id = signal.get("assignee_user_id") or data.get("suggested_owner_user_id") or None
    owner_name = signal.get("assignee_name") or data.get("suggested_owner_name") or "Unassigned"
    owner_name = str(owner_name).strip()[:100] or "Unassigned"
    if owner_id is not None:
        owner_id = str(owner_id).strip() or None
    return {
        "title": title[:200],
        "detail": detail or title,
        "suggested_owner_user_id": owner_id,
        "suggested_owner_name": owner_name,
    }


async def draft_decision(signal: dict, company_context: dict) -> dict:
    """Draft a decision card from a detected signal. Returns validated fields."""
    user = (
        f"Company: {json.dumps(company_context, default=str)}\n"
        f"Signal: {json.dumps(signal, default=str)}\n"
        "Draft the decision card JSON now."
    )
    raw = await complete(_DECISION_DRAFT_SYSTEM, user, max_tokens=800)
    if not raw:
        raise ValueError("Empty response from model")
    return _validate_decision_draft(_parse_extract_json(raw), signal)


async def draft_delegate(signal: dict, company_context: dict) -> dict:
    """Draft a delegate card from a task/blocker signal. Returns validated fields."""
    user = (
        f"Company: {json.dumps(company_context, default=str)}\n"
        f"Signal: {json.dumps(signal, default=str)}\n"
        "Draft the delegate card JSON now. Use the signal's assignee_user_id and assignee_name as the owner."
    )
    raw = await complete(_DELEGATE_DRAFT_SYSTEM, user, max_tokens=600)
    if not raw:
        raise ValueError("Empty response from model")
    return _validate_delegate_draft(_parse_extract_json(raw), signal)
