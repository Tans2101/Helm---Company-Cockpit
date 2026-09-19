"""Gmail draft replies: AI body when available, template fallback when not."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_gmail_draft")

import llm as helm_llm


def test_fallback_with_snippet_keeps_disclaimer_and_preview():
    body = helm_llm.fallback_gmail_draft_body(
        subject="Q3 pricing",
        snippet="Can we lock pricing by Friday?",
    )
    assert "Drafted in Trenston" in body
    assert "Can we lock pricing by Friday?" in body
    assert "Following up on:" not in body


def test_fallback_without_snippet_uses_subject_only():
    body = helm_llm.fallback_gmail_draft_body(subject="Q3 pricing", snippet="")
    assert "Drafted in Trenston" in body
    assert "Following up on: Q3 pricing" in body
    assert "On their last note:" not in body


@pytest.mark.asyncio
async def test_ai_draft_uses_model_text_and_appends_disclaimer():
    with patch.object(helm_llm, "anthropic_configured", return_value=True), \
         patch.object(helm_llm, "complete", new=AsyncMock(return_value="Thanks for the note — Friday works.\n\n[your name]")):
        body = await helm_llm.draft_gmail_reply(
            subject="Q3 pricing",
            to_email="buyer@acme.com",
            snippet="Can we lock pricing by Friday?",
        )
    assert "Friday works" in body
    assert "Drafted in Trenston" in body
    assert "[your name]" in body


@pytest.mark.asyncio
async def test_ai_draft_empty_snippet_still_calls_model_with_guardrail():
    with patch.object(helm_llm, "anthropic_configured", return_value=True), \
         patch.object(helm_llm, "complete", new=AsyncMock(return_value="Following up on Q3 pricing.\n\n[your name]")) as complete:
        body = await helm_llm.draft_gmail_reply(
            subject="Q3 pricing",
            to_email="buyer@acme.com",
            snippet="",
        )
    user_prompt = complete.await_args.args[1]
    assert "no preview available" in user_prompt
    assert "Following up on Q3 pricing" in body
    assert "Drafted in Trenston" in body


@pytest.mark.asyncio
async def test_ai_failure_falls_back_to_template():
    with patch.object(helm_llm, "anthropic_configured", return_value=True), \
         patch.object(helm_llm, "complete", new=AsyncMock(side_effect=RuntimeError("api down"))):
        body = await helm_llm.draft_gmail_reply(
            subject="Q3 pricing",
            to_email="buyer@acme.com",
            snippet="Can we talk?",
        )
    assert body == helm_llm.fallback_gmail_draft_body(
        subject="Q3 pricing", snippet="Can we talk?",
    )


@pytest.mark.asyncio
async def test_unconfigured_anthropic_uses_fallback():
    with patch.object(helm_llm, "anthropic_configured", return_value=False), \
         patch.object(helm_llm, "complete", new=AsyncMock()) as complete:
        body = await helm_llm.draft_gmail_reply(subject="Hello", snippet="")
    complete.assert_not_awaited()
    assert "Following up on: Hello" in body
