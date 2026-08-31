"""Verify Clerk session JWTs and load user profile from Clerk API."""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from jwt import PyJWKClient

from helm_config import HELM_CANONICAL_ORIGIN, HELM_PRIMARY_HOSTS

logger = logging.getLogger(__name__)

HELM_CLERK_JWKS_URL = "https://causal-caribou-2352.clerk.accounts.dev/.well-known/jwks.json"
CLERK_BAPI = "https://api.clerk.com/v1"


def _resolve_clerk_jwks_url() -> str:
    env = os.environ.get("CLERK_JWKS_URL", "").strip()
    if env:
        return env
    return HELM_CLERK_JWKS_URL


CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
CLERK_JWKS_URL = _resolve_clerk_jwks_url()
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")

HELM_CLERK_ORIGINS = {
    "https://helmcontrol.online",
    "https://www.helmcontrol.online",
    "https://apexcoach.tech",
    "https://www.apexcoach.tech",
    "https://helm-company-cockpit.vercel.app",
    "http://localhost:3000",
}

_jwks_client: PyJWKClient | None = None
_last_sync_status: dict[str, Any] | None = None


def clerk_configured() -> bool:
    return bool(CLERK_SECRET_KEY and CLERK_JWKS_URL)


def helm_frontend_origins() -> list[str]:
    """Origins Helm must register with Clerk for browser auth."""
    origins = {o for o in (
        *HELM_CLERK_ORIGINS,
        FRONTEND_URL,
        os.environ.get("APP_URL", "").strip().rstrip("/"),
    ) if o}
    return sorted(origins)


def primary_frontend_origin() -> str | None:
    """Production frontend origin — helmcontrol.online when configured."""
    for host in HELM_PRIMARY_HOSTS:
        for origin in helm_frontend_origins():
            if origin.startswith("https://") and host in origin:
                return origin
    if HELM_CANONICAL_ORIGIN and HELM_CANONICAL_ORIGIN.startswith("https://"):
        return HELM_CANONICAL_ORIGIN
    preferred = (FRONTEND_URL, os.environ.get("APP_URL", "").strip().rstrip("/"))
    for origin in preferred:
        if origin and origin.startswith("https://") and "localhost" not in origin:
            return origin
    for origin in helm_frontend_origins():
        if origin.startswith("https://") and "localhost" not in origin and "vercel.app" not in origin:
            return origin
    for origin in helm_frontend_origins():
        if origin.startswith("https://") and "localhost" not in origin:
            return origin
    return helm_frontend_origins()[0] if helm_frontend_origins() else None


def clerk_sync_status() -> dict[str, Any]:
    return dict(_last_sync_status or {"synced": False, "reason": "not_run"})


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not CLERK_JWKS_URL:
            raise RuntimeError("CLERK_JWKS_URL is not configured")
        _jwks_client = PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


def _bapi_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {CLERK_SECRET_KEY}"}


async def clerk_api_ok() -> bool:
    """True when CLERK_SECRET_KEY can reach the Clerk API (matches publishable key instance)."""
    if not CLERK_SECRET_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{CLERK_BAPI}/instance", headers=_bapi_headers())
            return r.status_code == 200
    except Exception:
        return False


async def fetch_clerk_instance() -> dict[str, Any] | None:
    if not clerk_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{CLERK_BAPI}/instance", headers=_bapi_headers())
            if r.status_code >= 400:
                return None
            return r.json()
    except Exception:
        logger.exception("Clerk instance GET failed")
        return None


def decode_clerk_jwt(token: str) -> dict[str, Any]:
    """Verify signature + expiry; return JWT payload."""
    try:
        signing_key = _jwks().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Clerk session expired — sign out and sign in again")
    except jwt.InvalidTokenError as exc:
        logger.warning("clerk jwt invalid: %s (jwks=%s)", exc, CLERK_JWKS_URL)
        raise ValueError(
            "Invalid Clerk session token — sign out, hard-refresh, and sign in again"
        ) from exc


async def fetch_clerk_user_profile(clerk_user_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{CLERK_BAPI}/users/{clerk_user_id}",
            headers=_bapi_headers(),
        )
    if r.status_code >= 400:
        raise ValueError(f"Clerk user lookup failed ({r.status_code}) — check CLERK_SECRET_KEY matches pk_live")
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


async def verify_clerk_session_token(token: str) -> dict[str, Any]:
    """Validate Clerk session JWT and return stable identity fields for Helm users."""
    payload = decode_clerk_jwt(token)
    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise ValueError("Clerk token missing sub")
    return await fetch_clerk_user_profile(clerk_user_id)


async def sync_clerk_satellite_domain(primary: str) -> dict[str, Any]:
    """Register Helm Vercel host as Clerk satellite domain so OAuth can redirect back."""
    from urllib.parse import urlparse

    host = urlparse(primary).hostname
    result: dict[str, Any] = {"attempted": True, "ok": False, "host": host}
    if not clerk_configured() or not host:
        result["reason"] = "not_configured"
        return result
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers = _bapi_headers()
            list_r = await client.get(f"{CLERK_BAPI}/domains", headers=headers)
            if list_r.status_code >= 400:
                result["reason"] = f"list_{list_r.status_code}"
                result["error"] = list_r.text[:300]
                return result
            domains = (list_r.json() or {}).get("data") or []
            result["existing_domains"] = [d.get("name") for d in domains]
            match = next((d for d in domains if d.get("name") == host), None)
            if match:
                result["ok"] = True
                result["reason"] = "already_registered"
                result["domain_id"] = match.get("id")
                return result
            add_r = await client.post(
                f"{CLERK_BAPI}/domains",
                headers=headers,
                json={"name": host, "is_satellite": True},
            )
            if add_r.status_code >= 400:
                result["reason"] = f"add_{add_r.status_code}"
                result["error"] = add_r.text[:500]
                return result
            created = add_r.json()
            result["ok"] = True
            result["reason"] = "created"
            result["domain_id"] = created.get("id")
            logger.info("Clerk satellite domain registered: %s", host)
            return result
    except Exception:
        logger.exception("Clerk satellite domain sync failed")
        result["reason"] = "exception"
        return result


async def sync_clerk_account_portal(primary: str) -> dict[str, Any]:
    """Point Clerk Account Portal post-auth redirects back to Helm (not accounts.dev)."""
    app_url = f"{primary.rstrip('/')}/app"
    result: dict[str, Any] = {"attempted": True, "ok": False}
    if not clerk_configured() or not primary:
        result["reason"] = "not_configured"
        return result
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers = _bapi_headers()
            get_r = await client.get(f"{CLERK_BAPI}/account_portal", headers=headers)
            if get_r.status_code >= 400:
                result["reason"] = f"get_{get_r.status_code}"
                result["error"] = get_r.text[:300]
                return result
            current = get_r.json()
            result["before"] = {
                "after_sign_in_url": current.get("after_sign_in_url"),
                "after_sign_up_url": current.get("after_sign_up_url"),
            }
            patch_body = {
                "after_sign_in_url": app_url,
                "after_sign_up_url": app_url,
                "logo_link_url": primary,
                "after_join_waitlist_url": app_url,
                "after_create_organization_url": app_url,
                "after_leave_organization_url": app_url,
            }
            patch_r = await client.patch(
                f"{CLERK_BAPI}/account_portal",
                headers=headers,
                json=patch_body,
            )
            if patch_r.status_code >= 400:
                result["reason"] = f"patch_{patch_r.status_code}"
                result["error"] = patch_r.text[:500]
                return result
            updated = patch_r.json() if patch_r.content else {}
            result["ok"] = True
            result["after"] = {
                "after_sign_in_url": updated.get("after_sign_in_url", app_url),
                "after_sign_up_url": updated.get("after_sign_up_url", app_url),
            }
            logger.info("Clerk account portal redirects → %s", app_url)
            return result
    except Exception:
        logger.exception("Clerk account portal sync failed")
        result["reason"] = "exception"
        return result


async def sync_clerk_instance() -> dict[str, Any]:
    """Register Helm Vercel origin with Clerk — required for dev instances on production URL."""
    global _last_sync_status
    wanted = helm_frontend_origins()
    primary = primary_frontend_origin()
    if not clerk_configured():
        _last_sync_status = {"synced": False, "reason": "clerk_not_configured"}
        return _last_sync_status
    if not wanted or not primary:
        _last_sync_status = {"synced": False, "reason": "no_frontend_origin"}
        return _last_sync_status

    status: dict[str, Any] = {
        "synced": False,
        "wanted_origins": wanted,
        "primary_origin": primary,
        "environment_type": None,
        "allowed_origins_before": [],
        "allowed_origins_after": [],
        "development_origin_set": None,
        "url_based_session_syncing": True,
        "warnings": [],
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers = _bapi_headers()
            r = await client.get(f"{CLERK_BAPI}/instance", headers=headers)
            if r.status_code >= 400:
                status["reason"] = f"instance_get_{r.status_code}"
                _last_sync_status = status
                return status

            inst = r.json()
            env_type = inst.get("environment_type")
            jwks_host = urlparse(CLERK_JWKS_URL).hostname or ""
            is_dev_fapi = jwks_host.endswith(".clerk.accounts.dev")
            current = set(inst.get("allowed_origins") or [])
            status["environment_type"] = env_type
            status["clerk_fapi_dev"] = is_dev_fapi
            status["allowed_origins_before"] = sorted(current)

            if is_dev_fapi or env_type == "development":
                status["warnings"].append(
                    "Clerk FAPI is a development instance (*.clerk.accounts.dev). "
                    "Sign-in works on Vercel after sync; create a Clerk production instance for a permanent fix."
                )

            merged = sorted(current | set(wanted))
            patch_body: dict[str, Any] = {
                "allowed_origins": merged,
                "url_based_session_syncing": True,
            }
            # development_origin only applies when BAPI reports development — not hybrid prod keys + dev FAPI.
            if env_type == "development":
                patch_body["development_origin"] = primary

            needs_patch = merged != sorted(current) or env_type == "development"
            if needs_patch:
                patch = await client.patch(
                    f"{CLERK_BAPI}/instance",
                    headers=headers,
                    json=patch_body,
                )
                if patch.status_code == 422 and "development_origin" in patch_body:
                    logger.warning("Clerk rejected development_origin — retrying without it")
                    retry_body = {k: v for k, v in patch_body.items() if k != "development_origin"}
                    patch = await client.patch(
                        f"{CLERK_BAPI}/instance",
                        headers=headers,
                        json=retry_body,
                    )
                if patch.status_code >= 400:
                    status["reason"] = f"instance_patch_{patch.status_code}"
                    status["patch_error"] = patch.text[:500]
                    _last_sync_status = status
                    logger.warning("Clerk instance PATCH failed (%s): %s", patch.status_code, patch.text[:200])
                    return status
                status["patched"] = True
                status["development_origin_set"] = patch_body.get("development_origin")
            else:
                status["patched"] = False

            verify = await client.get(f"{CLERK_BAPI}/instance", headers=headers)
            if verify.status_code == 200:
                after = verify.json()
                status["allowed_origins_after"] = sorted(after.get("allowed_origins") or [])
                status["environment_type"] = after.get("environment_type")

            missing = [o for o in wanted if o not in set(status["allowed_origins_after"])]
            status["missing_origins"] = missing
            status["synced"] = not missing
            if missing:
                status["reason"] = "origins_still_missing"
            else:
                status["reason"] = "ok"
                logger.info(
                    "Clerk instance synced for Helm (env=%s, origins=%s, dev_origin=%s)",
                    status["environment_type"],
                    ", ".join(wanted),
                    patch_body.get("development_origin"),
                )

            if is_dev_fapi and primary and not any(h in primary for h in HELM_PRIMARY_HOSTS):
                status["warnings"].append(
                    "Using Clerk development FAPI — register helmcontrol.online in Clerk Dashboard → Domains."
                )

            portal = await sync_clerk_account_portal(primary)
            status["account_portal"] = portal
            satellite = await sync_clerk_satellite_domain(primary)
            status["satellite_domain"] = satellite
            if not portal.get("ok"):
                status["warnings"].append(
                    "Could not auto-update Clerk redirect URLs — set After sign-in URL to "
                    f"{primary}/app in Clerk Dashboard → Configure → Paths."
                )
            if not satellite.get("ok"):
                status["warnings"].append(
                    f"Could not register {urlparse(primary).hostname} as Clerk satellite domain — "
                    "add it manually in Clerk Dashboard → Configure → Domains."
                )

            _last_sync_status = status
            return status
    except Exception:
        logger.exception("Clerk instance sync failed")
        status["reason"] = "exception"
        _last_sync_status = status
        return status


async def ensure_allowed_origins() -> bool:
    """Back-compat wrapper — sync full Clerk instance settings for Helm."""
    result = await sync_clerk_instance()
    return bool(result.get("synced"))


async def ensure_allowed_origins_legacy() -> bool:
    """Previous allowed_origins-only sync (kept for reference in tests)."""
    if not clerk_configured():
        return False
    wanted = set(helm_frontend_origins())
    if not wanted:
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers = _bapi_headers()
            r = await client.get(f"{CLERK_BAPI}/instance", headers=headers)
            if r.status_code >= 400:
                return False
            current = set(r.json().get("allowed_origins") or [])
            merged = sorted(current | wanted)
            if merged == sorted(current):
                return True
            patch = await client.patch(
                f"{CLERK_BAPI}/instance",
                headers=headers,
                json={"allowed_origins": merged},
            )
            return patch.status_code < 400
    except Exception:
        logger.exception("Clerk allowed_origins sync failed")
        return False
