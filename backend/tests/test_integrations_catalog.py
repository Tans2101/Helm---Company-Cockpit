"""Integration catalog merge and status tests."""
from __future__ import annotations

import integrations_catalog as cat


def test_merge_oauth_google_not_connected():
    ws = {"workspace_id": "ws1", "google_tokens": None, "quickbooks_tokens": None, "plan": "free"}
    ints = cat.merge_integrations(ws, google_configured=True, qb_configured=True)
    gcal = next(i for i in ints if i["id"] == "google_calendar")
    assert gcal["status"] == "not_connected"
    assert gcal["configured"] is True


def test_merge_oauth_unavailable_when_not_configured():
    ws = {"workspace_id": "ws1", "plan": "free"}
    ints = cat.merge_integrations(ws, google_configured=False, qb_configured=False)
    gcal = next(i for i in ints if i["id"] == "google_calendar")
    qb = next(i for i in ints if i["id"] == "quickbooks")
    assert gcal["status"] == "unavailable"
    assert qb["status"] == "unavailable"


def test_merge_oauth_connected():
    ws = {"workspace_id": "ws1", "google_tokens": {"access_token": "x"}, "quickbooks_tokens": {"access_token": "y"}}
    ints = cat.merge_integrations(ws, google_configured=True, qb_configured=True)
    gcal = next(i for i in ints if i["id"] == "google_calendar")
    qb = next(i for i in ints if i["id"] == "quickbooks")
    assert gcal["status"] == "connected"
    assert qb["status"] == "connected"


def test_coming_soon_integrations():
    ws = {"workspace_id": "ws1", "plan": "pro"}
    ints = cat.merge_integrations(ws, google_configured=True, qb_configured=True)
    github = next(i for i in ints if i["id"] == "github")
    assert github["coming_soon"] is True
    assert github["status"] == "coming_soon"
