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
    scope = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/gmail.readonly"
    ws = {
        "workspace_id": "ws1",
        "google_tokens": {"access_token": "x", "scope": scope},
        "quickbooks_tokens": {"access_token": "y"},
        "xero_tokens": {"access_token": "z", "tenant_id": "tenant-1", "tenant_name": "Demo"},
    }
    ints = cat.merge_integrations(ws, google_configured=True, qb_configured=True, xero_configured=True)
    gcal = next(i for i in ints if i["id"] == "google_calendar")
    gmail = next(i for i in ints if i["id"] == "gmail")
    qb = next(i for i in ints if i["id"] == "quickbooks")
    xero = next(i for i in ints if i["id"] == "xero")
    assert gcal["status"] == "connected"
    assert gmail["status"] == "connected"
    assert qb["status"] == "connected"
    assert xero["status"] == "connected"
    assert xero["tenant_name"] == "Demo"


def test_xero_needs_tenant_select():
    ws = {
        "workspace_id": "ws1",
        "xero_tokens": {
            "access_token": "z",
            "pending_tenants": [{"tenant_id": "a", "tenant_name": "A"}, {"tenant_id": "b", "tenant_name": "B"}],
        },
        "plan": "free",
    }
    ints = cat.merge_integrations(ws, google_configured=True, qb_configured=True, xero_configured=True)
    xero = next(i for i in ints if i["id"] == "xero")
    assert xero["status"] == "not_connected"
    assert xero.get("needs_tenant_select") is True
    assert xero["connected"] is False


def test_gmail_needs_reconsent_when_calendar_only():
    ws = {
        "workspace_id": "ws1",
        "google_tokens": {
            "access_token": "x",
            "scope": "https://www.googleapis.com/auth/calendar.readonly",
        },
        "plan": "free",
    }
    ints = cat.merge_integrations(ws, google_configured=True, qb_configured=True)
    gcal = next(i for i in ints if i["id"] == "google_calendar")
    gmail = next(i for i in ints if i["id"] == "gmail")
    assert gcal["status"] == "connected"
    assert gmail["status"] == "not_connected"
    assert gmail.get("needs_reconsent") is True
    assert gmail["connect_label"] == "Enable Gmail"


def test_merge_oauth_connected_when_sealed():
    sealed = {"_helm_enc": "v1", "payload": "gAAAAABnot-a-real-token-but-present"}
    ws = {"workspace_id": "ws1", "google_tokens": sealed, "quickbooks_tokens": sealed, "plan": "free"}
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
    gmail = next(i for i in ints if i["id"] == "gmail")
    assert gmail.get("coming_soon") is not True
    assert gmail["kind"] == "oauth"
    assert gmail["provider"] == "google"
    hubspot = next(i for i in ints if i["id"] == "hubspot")
    assert hubspot["kind"] == "oauth"
    assert hubspot["provider"] == "hubspot"
    assert hubspot.get("sync_action") is True
    assert not any(i["id"] == "salesforce" for i in ints)
    assert not any(i["id"] == "slack" for i in ints)


def test_hubspot_connected_when_tokens_present():
    ws = {
        "workspace_id": "ws1",
        "hubspot_tokens": {"access_token": "hs", "refresh_token": "r"},
        "hubspot_last_synced_at": "2026-09-01T00:00:00+00:00",
        "plan": "free",
    }
    ints = cat.merge_integrations(
        ws, google_configured=True, qb_configured=True, hubspot_configured=True,
    )
    hubspot = next(i for i in ints if i["id"] == "hubspot")
    assert hubspot["status"] == "connected"
    assert hubspot["last_synced_at"] == "2026-09-01T00:00:00+00:00"
