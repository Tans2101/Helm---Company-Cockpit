"""Canonical Helm URLs — single source of truth for production domain."""
from __future__ import annotations

import os

# www is the live Vercel host; apex redirects to www via DNS/Vercel.
HELM_CANONICAL_ORIGIN = os.environ.get(
    "HELM_CANONICAL_ORIGIN", "https://www.helmcontrol.online"
).strip().rstrip("/")

HELM_APP_PATH = "/app"
HELM_APP_URL = f"{HELM_CANONICAL_ORIGIN}{HELM_APP_PATH}"

HELM_PRIMARY_HOSTS = ("helmcontrol.online",)


def is_stale_deploy_url(url: str) -> bool:
    """True when Render/Vercel env still points at old preview hosts."""
    u = (url or "").lower()
    return not u or "vercel.app" in u or "onrender.com" in u


def registrable_cookie_domain(host: str | None) -> str | None:
    """Cookie domain that works for both apex and www (e.g. helmcontrol.online)."""
    if not host or host in ("localhost", "127.0.0.1"):
        return None
    if host.endswith(".vercel.app") or host.endswith(".onrender.com"):
        return None
    if host.startswith("www."):
        return host[4:]
    return host


def public_api_origin() -> str:
    """Public HTTPS origin for OAuth callbacks (Vercel proxies /api to Render)."""
    return HELM_CANONICAL_ORIGIN
