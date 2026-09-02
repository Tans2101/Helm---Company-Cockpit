import re
import uuid
import hmac
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import clerk_auth
import llm as helm_llm
from db import (
    APP_URL,
    ALLOW_DEMO_LOGIN,
    BILLING_ENFORCED,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    OAUTH_STATE_SECRET,
    CLERK_PUBLISHABLE_KEY,
    db,
    require_mongo,
)
from deps import (
    _allowed_auth_redirect,
    _looks_like_jwt,
    _upsert_clerk_user,
    _upsert_google_user,
    _user_from_clerk_jwt,
    _verify_state,
    clear_session_cookie,
    get_user,
    pack_of,
    perms_for,
    set_session_cookie,
    PACK_HOME,
    PACK_LABEL,
)
from helm_config import HELM_CANONICAL_ORIGIN, public_api_origin
from routes.integrations import _provider_config

logger = logging.getLogger("helm")

router = APIRouter()


class SessionInput(BaseModel):
    session_id: str


async def _issue_session(response: Response, user_id: str) -> str:
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": expires_at, "created_at": datetime.now(timezone.utc),
    })
    set_session_cookie(response, session_token)
    return session_token


def _auth_redirect_uri(_request: Request) -> str:
    return f"{public_api_origin()}/api/auth/google/callback"


@router.api_route("/clerk-proxy", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def clerk_fapi_proxy_root(request: Request):
    return await clerk_auth.proxy_clerk_fapi("v1/client", request)


@router.api_route("/clerk-proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def clerk_fapi_proxy(path: str, request: Request):
    """Browser Clerk SDK proxy — avoids broken clerk.* custom-domain TLS during provisioning."""
    return await clerk_auth.proxy_clerk_fapi(path, request)


@router.get("/auth/clerk-edge-secret")
async def clerk_edge_secret(request: Request):
    """Return CLERK_SECRET_KEY to Vercel edge middleware (bootstrap token required)."""
    token = request.headers.get("X-Clerk-Bootstrap", "").strip()
    bootstrap = clerk_auth.CLERK_PROXY_BOOTSTRAP
    if not bootstrap or not token or not hmac.compare_digest(token, bootstrap):
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")
    if not clerk_auth.CLERK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Clerk is not configured on Render")
    return {"clerk_secret_key": clerk_auth.CLERK_SECRET_KEY}


@router.get("/auth/config")
async def auth_config():
    clerk_on = clerk_auth.clerk_configured()
    google_on = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET) and not clerk_on
    provider = "clerk" if clerk_on else ("google" if google_on else "none")
    clerk_mode = clerk_auth.clerk_secret_mode() if clerk_on else None
    keys_aligned = (
        clerk_auth.clerk_keys_aligned(CLERK_PUBLISHABLE_KEY, clerk_auth.CLERK_JWKS_URL)
        if clerk_on and CLERK_PUBLISHABLE_KEY
        else None
    )
    mode_match = (
        clerk_auth.clerk_secret_publishable_mode_match(CLERK_PUBLISHABLE_KEY)
        if clerk_on and CLERK_PUBLISHABLE_KEY
        else None
    )
    ssl_ok = await clerk_auth.clerk_custom_domain_ssl_ok() if clerk_on else None
    return {
        "demo_login": ALLOW_DEMO_LOGIN,
        "clerk_enabled": clerk_on,
        "clerk_secret_mode": clerk_mode if clerk_on else None,
        "clerk_publishable_key": CLERK_PUBLISHABLE_KEY or None,
        "clerk_jwks_host": clerk_auth.clerk_jwks_host(),
        "clerk_keys_aligned": keys_aligned,
        "clerk_secret_mode_match": mode_match,
        "clerk_primary_origin": clerk_auth.clerk_primary_origin() if clerk_on else None,
        "clerk_post_auth_url": clerk_auth.clerk_post_auth_url() if clerk_on else None,
        "helm_canonical_origin": HELM_CANONICAL_ORIGIN,
        "clerk_multi_domain": clerk_auth.clerk_multi_domain_auth() if clerk_on else False,
        "clerk_api_ok": await clerk_auth.clerk_api_ok() if clerk_on else None,
        "clerk_jwks_ok": await clerk_auth.clerk_jwks_ok() if clerk_on else None,
        "clerk_custom_domain_ssl_ok": ssl_ok,
        "clerk_proxy_url": clerk_auth.clerk_proxy_url() if clerk_on else None,
        "clerk_use_proxy": (not ssl_ok) if clerk_on else None,
        "google_oauth": google_on,
        "provider": provider,
        "ai_ready": helm_llm.anthropic_configured(),
        "billing_enforced": BILLING_ENFORCED,
    }


@router.post("/auth/clerk")
async def clerk_login(request: Request, response: Response):
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    await require_mongo()
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="Missing Clerk session token")
    try:
        identity = await clerk_auth.verify_clerk_session_token(token)
    except ValueError as exc:
        logger.warning("clerk token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception:
        logger.exception("clerk token verification failed")
        raise HTTPException(
            status_code=401,
            detail="Invalid Clerk session — check Render CLERK_SECRET_KEY matches your pk_live key",
        )
    user = await _upsert_clerk_user(
        email=identity["email"],
        name=identity.get("name"),
        picture=identity.get("picture"),
        clerk_id=identity["clerk_id"],
    )
    await _issue_session(response, user["user_id"])
    return {"ok": True, "user_id": user["user_id"], "email": user["email"]}


@router.post("/auth/session")
async def process_session_removed():
    raise HTTPException(
        status_code=410,
        detail="Emergent session auth is retired. Use Google sign-in via /api/auth/google/login.",
    )


@router.post("/auth/demo-login")
async def demo_login_removed():
    raise HTTPException(status_code=410, detail="Demo login is disabled for production.")


@router.get("/auth/google/login")
async def google_login(request: Request, redirect: Optional[str] = None):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=400, detail="Google OAuth not configured")
    dest = redirect or (f"{APP_URL}/app" if APP_URL else "/app")
    if not _allowed_auth_redirect(dest):
        raise HTTPException(status_code=400, detail="Invalid redirect URL")
    state = jwt.encode(
        {
            "redirect": dest,
            "ts": int(datetime.now(timezone.utc).timestamp()),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        OAUTH_STATE_SECRET, algorithm="HS256",
    )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _auth_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    fail = f"{APP_URL or ''}/login?error=oauth"
    if error or not code or not state:
        return RedirectResponse(fail)
    try:
        payload = jwt.decode(state, OAUTH_STATE_SECRET, algorithms=["HS256"])
    except Exception:
        return RedirectResponse(fail)
    dest = payload.get("redirect") or (f"{APP_URL}/app" if APP_URL else "/app")
    if not _allowed_auth_redirect(dest):
        return RedirectResponse(fail)
    try:
        async with httpx.AsyncClient(timeout=30) as hc:
            token_res = await hc.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": _auth_redirect_uri(request),
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code >= 400:
                logger.error("google token error: %s", token_res.text[:400])
                return RedirectResponse(fail)
            tokens = token_res.json()
            access = tokens.get("access_token")
            if not access:
                return RedirectResponse(fail)
            info_res = await hc.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            if info_res.status_code >= 400:
                logger.error("google userinfo error: %s", info_res.text[:400])
                return RedirectResponse(fail)
            info = info_res.json()
        user = await _upsert_google_user(
            email=info.get("email"),
            name=info.get("name"),
            picture=info.get("picture"),
            google_sub=info.get("sub"),
        )
        response = RedirectResponse(dest)
        await _issue_session(response, user["user_id"])
        return response
    except HTTPException:
        return RedirectResponse(fail)
    except Exception:
        logger.exception("google oauth callback failed")
        return RedirectResponse(fail)


async def _user_session_payload(user: dict) -> dict:
    base = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "picture": user.get("picture"),
    }
    active = user.get("active_workspace_id")
    membership = None
    if active:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "workspace_id": active, "status": "active"}, {"_id": 0})
    if not membership:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "status": "active"}, {"_id": 0})
        if membership:
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"active_workspace_id": membership["workspace_id"]}},
            )
    if not membership:
        return {
            **base,
            "workspace_id": None,
            "needs_workspace": True,
            "role": None,
            "pack": None,
            "perms": [],
            "default_route": "/app/welcome",
            "pack_label": None,
        }
    pack = pack_of(membership)
    return {
        **base,
        "workspace_id": membership["workspace_id"],
        "needs_workspace": False,
        "role": membership["role"],
        "pack": pack,
        "perms": sorted(perms_for(pack)),
        "default_route": PACK_HOME.get(pack, "/app"),
        "pack_label": PACK_LABEL.get(pack, "Member"),
    }


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


@router.post("/auth/clerk/exchange")
async def clerk_exchange(request: Request, response: Response):
    """Clerk JWT → Helm session payload (+ optional httpOnly cookie)."""
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    await require_mongo()
    if CLERK_PUBLISHABLE_KEY and not clerk_auth.clerk_secret_publishable_mode_match(CLERK_PUBLISHABLE_KEY):
        raise HTTPException(
            status_code=503,
            detail=(
                f"CLERK_SECRET_KEY is {clerk_auth.clerk_secret_mode() or 'unknown'} but the publishable key "
                "is a different mode — use matching sk_live_/pk_live_ keys from the same Clerk instance on Render"
            ),
        )
    if not await clerk_auth.clerk_jwks_ok():
        raise HTTPException(
            status_code=503,
            detail="Clerk signing keys unavailable — check CLERK_SECRET_KEY on Render matches clerk.helmcontrol.online",
        )
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Clerk session token")
    if not _looks_like_jwt(token):
        raise HTTPException(
            status_code=401,
            detail="Clerk returned a non-JWT token — try signing out and back in",
        )
    user = await _user_from_clerk_jwt(token)
    await _issue_session(response, user["user_id"])
    return await _user_session_payload(user)


@router.get("/auth/me")
async def auth_me(user=Depends(get_user)):
    return await _user_session_payload(user)


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    clear_session_cookie(response)
    return {"ok": True}

@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, realmId: Optional[str] = None):
    cfg = _provider_config(provider)
    frontend = (APP_URL or public_api_origin()).rstrip("/")
    if not cfg or not code or not state:
        return RedirectResponse(f"{frontend}/integrations?error=oauth")
    verified = _verify_state(state)
    if not verified or verified[0] != provider:
        return RedirectResponse(f"{frontend}/integrations?error=state")
    workspace_id = verified[1]
    data = {"code": code, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "redirect_uri": cfg["redirect_uri"], "grant_type": "authorization_code"}
    try:
        async with httpx.AsyncClient() as hc:
            tr = await hc.post(cfg["token_uri"], data=data, headers={"Accept": "application/json"})
        tokens = tr.json()
        if realmId:
            tokens["realmId"] = realmId
        tokens["obtained_at"] = datetime.now(timezone.utc).isoformat()
        await db.workspaces.update_one({"workspace_id": workspace_id}, {"$set": {cfg["token_field"]: tokens}})
    except Exception:
        logger.exception("oauth token exchange failed")
        return RedirectResponse(f"{frontend}/integrations?error=token")
    return RedirectResponse(f"{frontend}/integrations?connected={provider}")
