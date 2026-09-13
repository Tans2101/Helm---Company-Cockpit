"""Document AI daily spend caps — skip parser, keep Claude."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_document_ai_limits")

import rate_limit  # noqa: E402
import llm as helm_llm  # noqa: E402


def _usage_db(rows: list[dict]):
    mock_db = MagicMock()

    async def count_documents(query):
        if "workspace_id" in query:
            return sum(1 for row in rows if row.get("workspace_id") == query["workspace_id"])
        return len(rows)

    async def insert_one(doc):
        rows.append(doc)

    mock_db.document_ai_usage.count_documents = AsyncMock(side_effect=count_documents)
    mock_db.document_ai_usage.insert_one = AsyncMock(side_effect=insert_one)
    return mock_db


def test_document_ai_workspace_and_global_caps():
    rows: list[dict] = []
    mock_db = _usage_db(rows)

    async def run():
        assert await rate_limit.document_ai_allowed(mock_db, "ws_a", global_limit=3, workspace_limit=2)
        await rate_limit.record_document_ai(mock_db, "ws_a")
        await rate_limit.record_document_ai(mock_db, "ws_a")
        assert not await rate_limit.document_ai_allowed(mock_db, "ws_a", global_limit=3, workspace_limit=2)
        assert await rate_limit.document_ai_allowed(mock_db, "ws_b", global_limit=3, workspace_limit=2)
        await rate_limit.record_document_ai(mock_db, "ws_b")
        assert not await rate_limit.document_ai_allowed(mock_db, "ws_b", global_limit=3, workspace_limit=2)

    asyncio.run(run())


def test_document_ai_zero_limit_is_kill_switch():
    mock_db = _usage_db([])

    async def run():
        assert not await rate_limit.document_ai_allowed(mock_db, "ws_a", global_limit=0, workspace_limit=8)
        assert not await rate_limit.document_ai_allowed(mock_db, "ws_a", global_limit=80, workspace_limit=0)

    asyncio.run(run())


def test_extract_skips_document_ai_when_disabled():
    claude = {
        "type": "expense",
        "amount": 12.5,
        "month": "2026-09",
        "category": "G&A",
        "name": "Render",
        "vendor": "Render",
        "note": "",
        "confidence": "high",
        "engine": "anthropic",
    }
    with patch.object(helm_llm, "anthropic_configured", return_value=True), patch.object(
        helm_llm, "extract_with_claude", new_callable=AsyncMock, return_value=claude,
    ), patch("google_document_ai.extract_invoice", new_callable=AsyncMock) as dai:
        out = asyncio.run(
            helm_llm.extract_financial_document(b"%PDF-1.4", "application/pdf", use_document_ai=False)
        )
    dai.assert_not_called()
    assert out["engine"] == "anthropic"
    assert out["amount"] == 12.5
