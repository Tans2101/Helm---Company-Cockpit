"""Verify Clerk session JWTs and load user profile from Clerk API."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

HELM_CLERK_JWKS_URL = "https://causal-caribou-2352.clerk.accounts.dev/.well-known/jwks.json"


def _resolve_clerk_jwks_url() -> str:
    env = os.environ.get("CLERK_JWKS_URL", "").strip()
    if not env or "apexcoach" in env:
        return HELM_CLERK_JWKS_URL
    if "causal-caribou" in env:
        return env
    return env or HELM_CLERK_JWKS_URL


CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
CLERK_JWKS_URL = _resolve_clerk_jwks_url()
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")

HELM_CLERK_ORIGINS = {
    "https://helm-company-cockpit.vercel.app",
    "http://localhost:3000",
}

_jwks_client: PyJWKClient | None = None


def clerk_configured() -> bool:
    return bool(CLERK_SECRET_KEY and CLERK_JWKS_URL)


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not CLERK_JWKS_URL:
            raise RuntimeError("CLERK_JWKS_URL is not configured")
        _jwks_client = PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


async def verify_clerk_session_token(token: str) -> dict[str, Any]:
    """Validate Clerk session JWT and return stable identity fields for Helm users."""
    signing_key = _jwks().get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise ValueError("Clerk token missing sub")

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"https://api.clerk.com/v1/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
        )
    if r.status_code >= 400:
        raise ValueError(f"Clerk user lookup failed ({r.status_code})")

    data = r.json()
    emails = data.get("email_addresses") or []
    primary_id = data.get("primary_email_address_id")
    primary = next((e for e in emails if e.get("id") == primary_id), emails[0] if emails else None)
    email = (primary or {}).get("email_address")
    if not email:
        raise ValueError("Clerk user has no email")

    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    name = f"{first} {last}".strip() or None

    return {
        "clerk_id": clerk_user_id,
        "email": email,
        "name": name,
        "picture": data.get("image_url"),
    }


async def ensure_allowed_origins() -> bool:
    """Register Helm frontend URL(s) with Clerk so browser sign-in works on Vercel."""
    if not clerk_configured():
        logger.info("Clerk origin sync skipped — secret/JWKS not configured")
        return False
    wanted = {o for o in (
        *HELM_CLERK_ORIGINS,
        FRONTEND_URL,
        os.environ.get("APP_URL", "").strip().rstrip("/"),
    ) if o}
    if not wanted:
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers = {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}
            r = await client.get("https://api.clerk.com/v1/instance", headers=headers)
            if r.status_code >= 400:
                logger.warning("Clerk instance GET failed (%s)", r.status_code)
                return False
            current = set(r.json().get("allowed_origins") or [])
            merged = sorted(current | wanted)
            if merged == sorted(current):
                logger.info("Clerk allowed_origins already include Helm URLs")
                return True
            patch = await client.patch(
                "https://api.clerk.com/v1/instance",
                headers=headers,
                json={"allowed_origins": merged},
            )
            if patch.status_code >= 400:
                logger.warning("Clerk allowed_origins PATCH failed (%s)", patch.status_code)
                return False
            logger.info("Clerk allowed_origins updated: %s", ", ".join(sorted(wanted)))
            return True
    except Exception:
        logger.exception("Clerk allowed_origins sync failed")
        return False
