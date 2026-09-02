"""Canonical integration definitions — merged with per-workspace OAuth state at read time."""
from __future__ import annotations

from typing import Any

# kind: oauth | platform | billing | coming_soon
INTEGRATION_CATALOG: list[dict[str, Any]] = [
    {
        "id": "google_calendar",
        "name": "Google Calendar",
        "category": "Calendar",
        "provider": "google",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Pull today's real meetings into Calendar and your morning briefing.",
        "value": "See your schedule and prep time without leaving Helm.",
        "cta_route": "/app/calendar",
        "cta_label": "Open calendar",
    },
    {
        "id": "quickbooks",
        "name": "QuickBooks",
        "category": "Finance",
        "provider": "quickbooks",
        "kind": "oauth",
        "oauth": True,
        "pro": True,
        "description": "Sync purchases and invoices into Financials — real burn and runway.",
        "value": "One-click sync replaces manual expense entry.",
        "cta_route": "/app/financials",
        "cta_label": "View financials",
        "sync_action": True,
    },
    {
        "id": "helm_ai",
        "name": "Helm AI (Anthropic)",
        "category": "Intelligence",
        "provider": "anthropic",
        "kind": "platform",
        "oauth": False,
        "pro": True,
        "description": "AI briefings, Ask Helm, and bill/receipt extraction.",
        "value": "Set ANTHROPIC_API_KEY on Render to unlock AI across the cockpit.",
        "cta_route": "/app/briefing",
        "cta_label": "Try briefing",
        "env_vars": ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"],
    },
    {
        "id": "document_storage",
        "name": "Document Storage (R2)",
        "category": "Finance",
        "provider": "r2",
        "kind": "platform",
        "oauth": False,
        "pro": True,
        "description": "Private bill and receipt uploads for AI extraction on Financials.",
        "value": "Upload a PDF or photo — Helm extracts amount, vendor, and category.",
        "cta_route": "/app/financials",
        "cta_label": "Upload a bill",
        "env_vars": ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_ENDPOINT"],
    },
    {
        "id": "team_email",
        "name": "Team Email (Resend)",
        "category": "Comms",
        "provider": "resend",
        "kind": "platform",
        "oauth": False,
        "pro": True,
        "description": "Invite emails when you add teammates from Team & Access.",
        "value": "New members get a branded invite with a link to sign in.",
        "cta_route": "/app/team",
        "cta_label": "Invite someone",
        "env_vars": ["RESEND_API_KEY", "SENDER_EMAIL"],
    },
    {
        "id": "paddle",
        "name": "Paddle Billing",
        "category": "Billing",
        "provider": "paddle",
        "kind": "billing",
        "oauth": False,
        "pro": True,
        "description": "Subscription checkout and customer portal when billing is enforced.",
        "value": "Manage Helm Pro activation from Billing.",
        "cta_route": "/app/billing",
        "cta_label": "Open billing",
        "env_vars": ["PADDLE_API_KEY", "PADDLE_CLIENT_TOKEN", "PADDLE_PRICE_ID", "PADDLE_WEBHOOK_SECRET"],
    },
    {
        "id": "gmail",
        "name": "Gmail",
        "category": "Email",
        "provider": "google",
        "kind": "coming_soon",
        "oauth": False,
        "pro": True,
        "description": "Executive email signal and follow-up surfacing.",
        "value": "Requires additional Google scopes — shipping after Calendar is stable.",
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
        "description": "PR velocity, release tracking, and task sync.",
        "value": "OAuth app setup required — on the roadmap.",
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
        "description": "Status pulls and delegation push to channels.",
        "value": "Slack app approval required — on the roadmap.",
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
        "description": "Pipeline, win rate, and forecast in Telemetry.",
        "value": "Salesforce connected app required — on the roadmap.",
        "coming_soon": True,
    },
]


def merge_integrations(
    workspace: dict,
    *,
    google_configured: bool,
    qb_configured: bool,
    anthropic_configured: bool,
    r2_configured: bool,
    resend_configured: bool,
    paddle_ready: bool,
    clerk_configured: bool,
) -> list[dict]:
    """Build integration cards with live connection/config status."""
    google_connected = bool(workspace.get("google_tokens"))
    qb_connected = bool(workspace.get("quickbooks_tokens"))
    qb_last_synced = workspace.get("qb_last_synced_at")

    platform_status = {
        "anthropic": anthropic_configured,
        "r2": r2_configured,
        "resend": resend_configured,
        "paddle": paddle_ready,
        "clerk": clerk_configured,
    }

    out: list[dict] = []
    for spec in INTEGRATION_CATALOG:
        item = dict(spec)
        item.setdefault("connected", False)
        kind = item.get("kind")

        if kind == "oauth":
            provider = item.get("provider")
            if provider == "google":
                item["connected"] = google_connected
                item["configured"] = google_configured
            elif provider == "quickbooks":
                item["connected"] = qb_connected
                item["configured"] = qb_configured
                item["last_synced_at"] = qb_last_synced
            else:
                item["configured"] = False
        elif kind == "platform":
            provider = item.get("provider")
            item["configured"] = platform_status.get(provider, False)
            item["connected"] = item["configured"]
        elif kind == "billing":
            item["configured"] = paddle_ready
            item["connected"] = workspace.get("plan") == "pro" and bool(
                workspace.get("paddle_subscription_id") or workspace.get("paddle_customer_id")
            )
        elif kind == "coming_soon":
            item["configured"] = False
            item["connected"] = False
        else:
            item["configured"] = True

        if item.get("coming_soon"):
            item["status"] = "coming_soon"
        elif kind in ("platform", "billing"):
            item["status"] = "ready" if item.get("configured") else "keys_needed"
        elif item.get("oauth"):
            if item.get("connected"):
                item["status"] = "connected"
            elif not item.get("configured"):
                item["status"] = "keys_needed"
            else:
                item["status"] = "not_connected"
        else:
            item["status"] = "not_connected"

        out.append(item)
    return out
