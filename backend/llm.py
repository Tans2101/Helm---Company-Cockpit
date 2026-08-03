"""Direct Anthropic API helpers — no Emergent LLM proxy."""
from __future__ import annotations

import os
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("EMERGENT_LLM_KEY") or ""
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

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
