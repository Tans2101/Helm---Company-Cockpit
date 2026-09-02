"""Integration catalog merge and status tests."""
from __future__ import annotations

import integrations_catalog as cat


def test_merge_oauth_google_not_connected():
    ws = {"workspace_id": "ws1", "google_tokens": None, "quickbooks_tokens": None, "plan": "free"}
    ints = cat.merge_integrations(
        ws,
        google_configured=True,
        qb_configured=True,
        anthropic_configured=False,
        r2_configured=False,
        resend_configured=False,
        paddle_ready=False,
        clerk_configured=True,
    )
    gcal = next(i for i in ints if i["id"] == "google_calendar")
    assert gcal["status"] == "not_connected"
    assert gcal["configured"] is True


def test_merge_platform_anthropic_keys_needed():
    ws = {"workspace_id": "ws1", "plan": "free"}
    ints = cat.merge_integrations(
        ws,
        google_configured=False,
        qb_configured=False,
        anthropic_configured=False,
        r2_configured=True,
        resend_configured=True,
        paddle_ready=True,
        clerk_configured=True,
    )
    ai = next(i for i in ints if i["id"] == "helm_ai")
    r2 = next(i for i in ints if i["id"] == "document_storage")
    assert ai["status"] == "keys_needed"
    assert r2["status"] == "ready"


def test_coming_soon_integrations():
    ws = {"workspace_id": "ws1", "plan": "pro"}
    ints = cat.merge_integrations(
        ws,
        google_configured=True,
        qb_configured=True,
        anthropic_configured=True,
        r2_configured=True,
        resend_configured=True,
        paddle_ready=True,
        clerk_configured=True,
    )
    github = next(i for i in ints if i["id"] == "github")
    assert github["coming_soon"] is True
    assert github["status"] == "coming_soon"
