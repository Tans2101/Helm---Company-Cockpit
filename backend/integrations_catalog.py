"""Canonical integration definitions — user-facing connectable services only.

Platform infrastructure (Anthropic, R2, Resend, Paddle) is configured by the Helm
host and must not appear as end-user "integrations".
"""
from __future__ import annotations

from typing import Any

import credential_crypto as cred_crypto

# kind: oauth | coming_soon
USER_INTEGRATIONS: list[dict[str, Any]] = [
    {
        "id": "google_calendar",
        "name": "Google Calendar",
        "category": "Calendar",
        "provider": "google",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Sync your real meetings into Helm Calendar and your daily briefing. Connecting Google also enables Gmail for the briefing.",
        "value": "See today's schedule, prep time, and deadlines in one place — no tab switching.",
        "cta_route": "/app/calendar",
        "cta_label": "Open calendar",
        "connect_label": "Connect Google",
    },
    {
        "id": "gmail",
        "name": "Gmail",
        "category": "Email",
        "provider": "google",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Surface important threads and external follow-ups in your morning briefing.",
        "value": "Stay on top of customer and investor email without living in your inbox.",
        "cta_route": "/app",
        "cta_label": "Open briefing",
        "connect_label": "Connect Gmail",
    },
    {
        "id": "quickbooks",
        "name": "QuickBooks",
        "category": "Finance",
        "provider": "quickbooks",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Pull purchases and invoices from your QuickBooks company into Financials. Use QuickBooks or Xero — you typically connect one accounting system.",
        "value": "Real burn, runway, and expense categories — synced from the books you already use.",
        "cta_route": "/app/financials",
        "cta_label": "View financials",
        "connect_label": "Connect QuickBooks",
        "sync_action": True,
    },
    {
        "id": "xero",
        "name": "Xero",
        "category": "Finance",
        "provider": "xero",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Pull invoices and bills from Xero into Financials — the global alternative to QuickBooks (UK, AU, NZ, and beyond).",
        "value": "Same Financials, Decision Engine, and reports pipeline as QuickBooks — pick the ledger you already run.",
        "cta_route": "/app/financials",
        "cta_label": "View financials",
        "connect_label": "Connect Xero",
        "sync_action": True,
    },
    {
        "id": "github",
        "name": "GitHub",
        "category": "Engineering",
        "provider": "github",
        "kind": "coming_soon",
        "oauth": False,
        "pro": True,
        "description": "Track PR velocity, releases, and engineering delivery in Telemetry.",
        "value": "Connect your repos to see shipping pace alongside business KPIs.",
        "coming_soon": True,
    },
    # Slack Incoming Webhook alerts are configured on the Integrations page UI
    # (not listed here) — do not re-add a coming_soon Slack OAuth card.
    {
        "id": "hubspot",
        "name": "HubSpot",
        "category": "Sales",
        "provider": "hubspot",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Pull HubSpot CRM deals into Helm Pipeline and Telemetry — built for SMB and mid-market teams.",
        "value": "Open pipeline, stage, and win/loss land in the same board as deals you create manually.",
        "cta_route": "/app/sales",
        "cta_label": "Open pipeline",
        "connect_label": "Connect HubSpot",
        "sync_action": True,
    },
]

# Back-compat alias for any code still importing INTEGRATION_CATALOG
INTEGRATION_CATALOG = USER_INTEGRATIONS


def merge_integrations(
    workspace: dict,
    *,
    google_configured: bool,
    qb_configured: bool,
    xero_configured: bool = False,
    hubspot_configured: bool = False,
    **_kwargs,
) -> list[dict]:
    """Build user integration cards with live connection status."""
    google_connected = cred_crypto.credentials_present(workspace.get("google_tokens"))
    qb_connected = cred_crypto.credentials_present(workspace.get("quickbooks_tokens"))
    qb_last_synced = workspace.get("qb_last_synced_at")
    xero_tokens = None
    if cred_crypto.credentials_present(workspace.get("xero_tokens")):
        try:
            xero_tokens = cred_crypto.unseal_credentials(workspace.get("xero_tokens"))
        except cred_crypto.CredentialCryptoError:
            xero_tokens = None
    xero_connected = bool(xero_tokens and xero_tokens.get("tenant_id"))
    xero_pending = bool(xero_tokens and not xero_tokens.get("tenant_id") and xero_tokens.get("pending_tenants"))
    xero_last_synced = workspace.get("xero_last_synced_at")
    hubspot_connected = cred_crypto.credentials_present(workspace.get("hubspot_tokens"))
    hubspot_last_synced = workspace.get("hubspot_last_synced_at")
    google_tokens = None
    if google_connected:
        try:
            google_tokens = cred_crypto.unseal_credentials(workspace.get("google_tokens"))
        except cred_crypto.CredentialCryptoError:
            google_tokens = None
    gmail_connected = bool(
        google_tokens and "gmail.readonly" in (google_tokens.get("scope") or "")
    )

    oauth_configured = {
        "google": google_configured,
        "quickbooks": qb_configured,
        "xero": xero_configured,
        "hubspot": hubspot_configured,
    }

    out: list[dict] = []
    for spec in USER_INTEGRATIONS:
        item = dict(spec)
        item.setdefault("connected", False)
        kind = item.get("kind")

        if kind == "oauth":
            provider = item.get("provider")
            item["configured"] = oauth_configured.get(provider, False)
            if item.get("id") == "gmail":
                item["connected"] = gmail_connected
                if google_connected and not gmail_connected:
                    item["connect_label"] = "Enable Gmail"
                    item["needs_reconsent"] = True
            elif provider == "google":
                item["connected"] = google_connected
            elif provider == "quickbooks":
                item["connected"] = qb_connected
                item["last_synced_at"] = qb_last_synced
            elif provider == "xero":
                item["connected"] = xero_connected
                item["last_synced_at"] = xero_last_synced
                item["needs_tenant_select"] = xero_pending
                if xero_tokens and xero_tokens.get("tenant_name"):
                    item["tenant_name"] = xero_tokens.get("tenant_name")
            elif provider == "hubspot":
                item["connected"] = hubspot_connected
                item["last_synced_at"] = hubspot_last_synced
        elif kind == "coming_soon":
            item["configured"] = False
            item["connected"] = False
        else:
            item["configured"] = True

        if item.get("coming_soon"):
            item["status"] = "coming_soon"
        elif item.get("oauth"):
            if item.get("connected"):
                item["status"] = "connected"
            elif item.get("needs_tenant_select"):
                item["status"] = "not_connected"
            elif not item.get("configured"):
                item["status"] = "unavailable"
            else:
                item["status"] = "not_connected"
        else:
            item["status"] = "not_connected"

        out.append(item)
    return out
