"""FastAPI dependencies: auth, permissions, cookies, OAuth helpers."""
import os
import re
import uuid
import hmac
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse

import clerk_auth
from fastapi import Request, Response, HTTPException, Depends

from db import (
    APP_URL,
    BILLING_ENFORCED,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    CORS_ORIGINS,
    FRONTEND_URL,
    OAUTH_STATE_SECRET,
    SETUP_SECRET,
    db,
)
from helm_config import registrable_cookie_domain

logger = logging.getLogger("helm")

# In-memory join-code rate limit: IP -> list of attempt timestamps
_join_attempts: dict[str, list[float]] = defaultdict(list)
_JOIN_RATE_LIMIT = 10
_JOIN_RATE_WINDOW = 15 * 60


def _session_cookie_domain() -> str | None:
    # When Clerk redirects to apexcoach but the app also runs on helmcontrol, use host-only cookies.
    if clerk_auth.clerk_multi_domain_auth():
        return None
    explicit = os.environ.get("COOKIE_DOMAIN", "").strip()
    if explicit:
        return explicit
    for raw in (
        clerk_auth.primary_frontend_origin(),
        FRONTEND_URL,
        APP_URL,
    ):
        if not raw:
            continue
        host = urlparse(raw).hostname
        domain = registrable_cookie_domain(host)
        if domain:
            return domain
    return None


def set_session_cookie(response: Response, token: str):
    kwargs = dict(
        key="session_token", value=token, httponly=True,
        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE,
        path="/", max_age=7 * 24 * 60 * 60,
    )
    domain = _session_cookie_domain()
    if domain:
        kwargs["domain"] = domain
    response.set_cookie(**kwargs)


def clear_session_cookie(response: Response):
    kwargs = dict(
        key="session_token", path="/",
        httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE,
    )
    domain = _session_cookie_domain()
    if domain:
        kwargs["domain"] = domain
    response.delete_cookie(**kwargs)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _check_join_rate_limit(ip: str):
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - _JOIN_RATE_WINDOW
    attempts = [t for t in _join_attempts[ip] if t > window_start]
    _join_attempts[ip] = attempts
    if len(attempts) >= _JOIN_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many join attempts. Try again later.")
    attempts.append(now)
    _join_attempts[ip] = attempts
# ------------------------- Access packs / permissions -------------------------
# Every employee can do daily work: read, move/create their tasks, ask Helm, post a daily update.
BASE_PERMS = {"read", "tasks:move", "tasks:create", "ask:use", "updates:write"}
PACK_PERMS = {
    "member": BASE_PERMS,
    "finance": BASE_PERMS | {"finance:write"},
    "hr": BASE_PERMS | {"people:write"},
    "sales": BASE_PERMS | {"sales:write"},
    "ops": BASE_PERMS | {"ops:write"},
    "exec": BASE_PERMS | {
        "decisions:act", "briefing:generate", "reports:pack",
        "members:invite", "tasks:assign",
    },
    "owner": BASE_PERMS | {
        "finance:write", "people:write", "sales:write", "ops:write",
        "decisions:act", "briefing:generate", "reports:pack",
        "integrations:manage", "billing:manage",
        "members:invite", "members:manage", "tasks:assign", "workspace:edit",
    },
}
# Where each pack lands after login. Operators start on their lane or "My Day".
PACK_HOME = {"owner": "/app", "exec": "/app", "member": "/app/me",
             "finance": "/app/financials", "hr": "/app/people",
             "sales": "/app/sales", "ops": "/app/me"}
PACK_LABEL = {"owner": "Owner", "exec": "Executive", "finance": "Finance",
              "hr": "People/HR", "sales": "Sales", "ops": "Operations", "member": "Member"}
VALID_PACKS = set(PACK_PERMS.keys())


def pack_of(membership: dict) -> str:
    """Resolve a membership's access pack, defaulting for legacy owner/member rows."""
    p = membership.get("pack")
    if p in VALID_PACKS:
        return p
    return "owner" if membership.get("role") == "owner" else "member"


def perms_for(pack: str):
    return PACK_PERMS.get(pack, PACK_PERMS["member"])


# ------------------------- OAuth state signing (CSRF) -------------------------
_STATE_SECRET = OAUTH_STATE_SECRET.encode()


def _allowed_auth_redirect(url: str) -> bool:
    """Only allow post-login redirects to our frontend origins (open-redirect guard)."""
    import server

    if not url:
        return False
    if url.startswith("/") and not url.startswith("//"):
        return True
    app_url = server.APP_URL
    cors_origins = server.CORS_ORIGINS
    bases = {app_url.rstrip("/")} if app_url else set()
    bases.update(o.rstrip("/") for o in cors_origins if o)
    bases.update(clerk_auth.helm_frontend_origins())
    for base in bases:
        if url == base or url.startswith(base + "/"):
            return True
    return False


def _require_setup_secret(request: Request) -> None:
    if not SETUP_SECRET:
        raise HTTPException(status_code=503, detail="Setup endpoint disabled (set SETUP_SECRET on Render)")
    provided = request.headers.get("X-Setup-Secret", "").strip()
    if not provided or not hmac.compare_digest(provided, SETUP_SECRET):
        raise HTTPException(status_code=401, detail="Invalid setup secret")


def _sign_state(provider: str, workspace_id: str) -> str:
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    body = f"{provider}:{workspace_id}:{ts}"
    sig = hmac.new(_STATE_SECRET, body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}:{sig}"


def _verify_state(state: str, max_age: int = 600):
    try:
        provider, workspace_id, ts, sig = state.split(":")
    except (ValueError, AttributeError):
        return None
    body = f"{provider}:{workspace_id}:{ts}"
    expected = hmac.new(_STATE_SECRET, body.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(expected, sig):
        return None
    if int(datetime.now(timezone.utc).timestamp()) - int(ts) > max_age:
        return None
    return provider, workspace_id

# ------------------------- Auth / principal -------------------------
def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


async def _find_user_by_identity(
    email: str,
    google_sub: Optional[str] = None,
    clerk_id: Optional[str] = None,
):
    """Stable identity: Clerk id / Google sub first, then normalized email."""
    if clerk_id:
        by_clerk = await db.users.find_one({"clerk_id": clerk_id}, {"_id": 0})
        if by_clerk:
            return by_clerk
    if google_sub:
        by_sub = await db.users.find_one({"google_sub": google_sub}, {"_id": 0})
        if by_sub:
            return by_sub
    if not email:
        return None
    by_email = await db.users.find_one({"email": email}, {"_id": 0})
    if by_email:
        return by_email
    return await db.users.find_one(
        {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}, {"_id": 0}
    )


async def _upsert_clerk_user(*, email: str, name: Optional[str], picture: Optional[str], clerk_id: str):
    email = _normalize_email(email)
    if not email or not clerk_id:
        raise HTTPException(status_code=400, detail="Clerk account email is required")
    existing = await _find_user_by_identity(email, clerk_id=clerk_id)
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        user_id = existing["user_id"]
        updates = {
            "email": email,
            "name": name or existing.get("name"),
            "picture": picture or existing.get("picture"),
            "clerk_id": clerk_id,
        }
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "clerk_id": clerk_id, "created_at": now,
        })
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    await _bootstrap(user)
    return user


async def _upsert_google_user(*, email: str, name: Optional[str], picture: Optional[str], google_sub: Optional[str]):
    email = _normalize_email(email)
    if not email:
        raise HTTPException(status_code=400, detail="Google account email is required")
    existing = await _find_user_by_identity(email, google_sub)
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        user_id = existing["user_id"]
        updates = {"email": email, "name": name or existing.get("name"), "picture": picture or existing.get("picture")}
        if google_sub:
            updates["google_sub"] = google_sub
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "google_sub": google_sub, "created_at": now,
        })
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    await _bootstrap(user)
    return user


async def _user_from_clerk_jwt(token: str):
    """Authenticate via Clerk session JWT (no Helm cookie required)."""
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=401, detail="Clerk is not configured")
    try:
        payload = await clerk_auth.decode_clerk_jwt(token)
        clerk_id = payload.get("sub")
        if not clerk_id:
            raise ValueError("Clerk token missing sub")
        existing = await db.users.find_one({"clerk_id": clerk_id}, {"_id": 0})
        if existing:
            await _bootstrap(existing)
            return existing
        identity = await clerk_auth.fetch_clerk_user_profile(clerk_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("clerk jwt auth failed")
        raise HTTPException(
            status_code=401,
            detail="Clerk sign-in failed — check Render CLERK_SECRET_KEY matches your Clerk publishable key",
        )
    try:
        return await _upsert_clerk_user(
            email=identity["email"],
            name=identity.get("name"),
            picture=identity.get("picture"),
            clerk_id=identity["clerk_id"],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("clerk user upsert failed for %s", identity.get("email"))
        raise HTTPException(
            status_code=503,
            detail="Could not save your account — database unavailable. Try again in a moment.",
        )


async def _user_from_request(request: Request):
    auth = request.headers.get("Authorization", "")
    bearer = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if bearer and _looks_like_jwt(bearer):
        try:
            return await _user_from_clerk_jwt(bearer)
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
            # Fall back to Helm session cookie when Clerk JWT is stale/invalid.

    token = request.cookies.get("session_token")
    if not token and bearer:
        token = bearer
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def _activate_invites(user):
    """Attach any pending email invites to this user (join inviting workspace)."""
    email = _normalize_email(user.get("email") or "")
    if not email:
        return
    await db.memberships.update_many(
        {"email": email, "status": "invited"},
        {"$set": {"user_id": user["user_id"], "status": "active",
                  "joined_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Legacy mixed-case invite emails
    await db.memberships.update_many(
        {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}, "status": "invited"},
        {"$set": {"user_id": user["user_id"], "email": email, "status": "active",
                  "joined_at": datetime.now(timezone.utc).isoformat()}},
    )


async def _bootstrap(user):
    """Activate any pending email invites for this user. No silent company creation —
    genuinely new users choose to create a company or join via code (see /auth/me)."""
    await _activate_invites(user)


async def get_user(request: Request):
    """Authenticated user, invites activated — but does NOT require a workspace."""
    user = await _user_from_request(request)
    await _activate_invites(user)
    return user


async def get_principal(request: Request):
    user = await _user_from_request(request)
    await _bootstrap(user)
    active = user.get("active_workspace_id")
    membership = None
    if active:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "workspace_id": active, "status": "active"}, {"_id": 0})
    if not membership:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "status": "active"}, {"_id": 0})
        if membership:
            active = membership["workspace_id"]
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": active}})
    if not membership:
        raise HTTPException(status_code=403, detail="No workspace")
    return {
        "user_id": user["user_id"], "email": user["email"], "name": user.get("name"),
        "picture": user.get("picture"), "workspace_id": membership["workspace_id"],
        "role": membership["role"], "pack": pack_of(membership),
    }


def require(action: str):
    async def dep(principal=Depends(get_principal)):
        if action not in perms_for(principal["pack"]):
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return principal
    return dep


def workspace_is_pro(ws_or_plan) -> bool:
    """True when billing is off (dev) or workspace has an active paid plan."""
    if not BILLING_ENFORCED:
        return True
    plan = ws_or_plan.get("plan") if isinstance(ws_or_plan, dict) else ws_or_plan
    return plan == "pro"


async def require_pro(principal=Depends(get_principal)):
    if not BILLING_ENFORCED:
        return principal
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Helm subscription required")
    return principal


def require_pro_perm(action: str):
    async def dep(principal=Depends(get_principal)):
        if action not in perms_for(principal["pack"]):
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        if BILLING_ENFORCED:
            c = await get_ws(principal["workspace_id"])
            if c["plan"] != "pro":
                raise HTTPException(status_code=403, detail="Helm subscription required")
        return principal
    return dep


async def get_ws(workspace_id: str):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws

async def require_workspace(user=Depends(get_user)):
    ws_id = user.get("active_workspace_id")
    membership = None
    if ws_id:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "workspace_id": ws_id, "status": "active"}, {"_id": 0})
    if not membership:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "status": "active"}, {"_id": 0})
    if not membership:
        raise HTTPException(status_code=403, detail="No workspace")
    return membership["workspace_id"]


async def get_membership(user=Depends(get_user), workspace_id: str = Depends(require_workspace)):
    m = await db.memberships.find_one(
        {"user_id": user["user_id"], "workspace_id": workspace_id, "status": "active"}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=403, detail="No workspace membership")
    return m

