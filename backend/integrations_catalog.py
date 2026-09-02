"""Canonical integration definitions — user-facing connectable services only.

Platform infrastructure (Anthropic, R2, Resend, Paddle) is configured by the Helm
host and must not appear as end-user "integrations".
"""
from __future__ import annotations

from typing import Any

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
        "description": "Sync your real meetings into Helm Calendar and your daily briefing.",
        "value": "See today's schedule, prep time, and deadlines in one place — no tab switching.",
        "cta_route": "/app/calendar",
        "cta_label": "Open calendar",
        "connect_label": "Connect Google Calendar",
    },
    {
        "id": "quickbooks",
        "name": "QuickBooks",
        "category": "Finance",
        "provider": "quickbooks",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Pull purchases and invoices from your QuickBooks company into Financials.",
        "value": "Real burn, runway, and expense categories — synced from the books you already use.",
        "cta_route": "/app/financials",
        "cta_label": "View financials",
        "connect_label": "Connect QuickBooks",
        "sync_action": True,
    },
    {
        "id": "gmail",
        "name": "Gmail",
        "category": "Email",
        "provider": "google",
        "kind": "coming_soon",
        "oauth": False,
        "pro": True,
        "description": "Surface important threads, follow-ups, and executive email signals in Helm.",
        "value": "Stay on top of customer and investor email without living in your inbox.",
        "coming_soon": True,
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
    {
        "id": "slack",
        "name": "Slack",
        "category": "Comms",
        "provider": "slack",
        "kind": "coming_soon",
        "oauth": False,
        "pro": True,
        "description": "Post daily updates and decision alerts to the channels your team already uses.",
        "value": "Keep Helm as the source of truth while updates flow where people work.",
        "coming_soon": True,
    },
    {
        "id": "salesforce",
        "name": "Salesforce",
        "category": "Sales",
        "provider": "salesforce",
        "kind": "coming_soon",
        "oauth": False,
        "pro": True,
        "description": "Import pipeline, win rate, and forecast into Telemetry and Reports.",
        "value": "One view of revenue from CRM through to cash in Financials.",
        "coming_soon": True,
    },
]

# Back-compat alias for any code still importing INTEGRATION_CATALOG
INTEGRATION_CATALOG = USER_INTEGRATIONS


def merge_integrations(
    workspace: dict,
    *,
    google_configured: bool,
    qb_configured: bool,
    **_kwargs,
) -> list[dict]:
    """Build user integration cards with live connection status."""
    google_connected = bool(workspace.get("google_tokens"))
    qb_connected = bool(workspace.get("quickbooks_tokens"))
    qb_last_synced = workspace.get("qb_last_synced_at")

    oauth_configured = {
        "google": google_configured,
        "quickbooks": qb_configured,
    }

    out: list[dict] = []
    for spec in USER_INTEGRATIONS:
        item = dict(spec)
        item.setdefault("connected", False)
        kind = item.get("kind")

        if kind == "oauth":
            provider = item.get("provider")
            item["configured"] = oauth_configured.get(provider, False)
            if provider == "google":
                item["connected"] = google_connected
            elif provider == "quickbooks":
                item["connected"] = qb_connected
                item["last_synced_at"] = qb_last_synced
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
            elif not item.get("configured"):
                item["status"] = "unavailable"
            else:
                item["status"] = "not_connected"
        else:
            item["status"] = "not_connected"

        out.append(item)
    return out
