import os
import re
import uuid
import json
import html
import hmac
import hashlib
import secrets
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode
from collections import defaultdict

import httpx
import jwt
import resend
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse, RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr

import llm as helm_llm
import clerk_auth
from seed_data import build_workspace, sample_financial_entries, gen_join_code

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

def _resolve_mongo_url() -> str:
    """Use MONGO_HOST (Render blueprint) or MONGO_URL (Atlas)."""
    host = os.environ.get("MONGO_HOST", "").strip()
    if host:
        return f"mongodb://{host}:27017"
    if url := os.environ.get("MONGO_URL", "").strip():
        return url
    raise RuntimeError("Set MONGO_URL (Atlas) or sync render.yaml for MONGO_HOST")


mongo_url = _resolve_mongo_url()
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=2000,
    connectTimeoutMS=2000,
    socketTimeoutMS=5000,
)
db = client[os.environ['DB_NAME']]

SESSION_SECRET = os.environ.get('SESSION_SECRET', 'change-me-in-production')
FRONTEND_URL = os.environ.get('FRONTEND_URL', '')
ALLOW_DEMO_LOGIN = os.environ.get("ALLOW_DEMO_LOGIN", "false").lower() in ("1", "true", "yes")
DEMO_RESET_ENABLED = os.environ.get("DEMO_RESET_ENABLED", "false").lower() in ("1", "true", "yes")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET", "")
if not OAUTH_STATE_SECRET:
    OAUTH_STATE_SECRET = SESSION_SECRET
APP_URL = (os.environ.get("APP_URL") or FRONTEND_URL or "").rstrip("/")
PRO_PRICE = float(os.environ.get("PRO_PRICE", "8"))
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", "").strip() or None

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')  # unused; kept so old envs don't crash on import
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
QB_CLIENT_ID = os.environ.get('QUICKBOOKS_CLIENT_ID', '')
QB_CLIENT_SECRET = os.environ.get('QUICKBOOKS_CLIENT_SECRET', '')
QB_ENV = os.environ.get('QUICKBOOKS_ENV', 'sandbox')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
PADDLE_API_KEY = os.environ.get('PADDLE_API_KEY', '')
PADDLE_CLIENT_TOKEN = os.environ.get('PADDLE_CLIENT_TOKEN', '')
PADDLE_PRICE_ID = os.environ.get('PADDLE_PRICE_ID', '')
PADDLE_WEBHOOK_SECRET = os.environ.get('PADDLE_WEBHOOK_SECRET', '')
PADDLE_ENV = os.environ.get('PADDLE_ENV', 'sandbox')
PADDLE_API_BASE = "https://sandbox-api.paddle.com" if PADDLE_ENV == "sandbox" else "https://api.paddle.com"

app = FastAPI()
api_router = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helm")

# In-memory join-code rate limit: IP -> list of attempt timestamps
_join_attempts: dict[str, list[float]] = defaultdict(list)
_JOIN_RATE_LIMIT = 10
_JOIN_RATE_WINDOW = 15 * 60


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token", value=token, httponly=True,
        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE,
        path="/", max_age=7 * 24 * 60 * 60,
    )


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
if not os.environ.get("OAUTH_STATE_SECRET") and COOKIE_SECURE and SESSION_SECRET == "change-me-in-production":
    logger.warning("Set OAUTH_STATE_SECRET and SESSION_SECRET in production")

_STATE_SECRET = OAUTH_STATE_SECRET.encode()


def _allowed_auth_redirect(url: str) -> bool:
    """Only allow post-login redirects to our frontend origins (open-redirect guard)."""
    if not url:
        return False
    if url.startswith("/") and not url.startswith("//"):
        return True
    bases = {APP_URL.rstrip("/")} if APP_URL else set()
    bases.update(o.rstrip("/") for o in CORS_ORIGINS if o)
    for base in bases:
        if url == base or url.startswith(base + "/"):
            return True
    return False


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


# ------------------------- Email (Resend) -------------------------
def _invite_email_html(inviter_name: str, workspace_name: str, role: str, app_url: str) -> str:
    inviter_name = html.escape(inviter_name)
    workspace_name = html.escape(workspace_name)
    role = html.escape(role)
    app_url = html.escape(app_url, quote=True)
    return f"""\
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#09090b;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#09090b;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#121214;border:1px solid rgba(255,255,255,0.08);border-radius:14px;overflow:hidden;">
<tr><td style="padding:32px 36px 8px 36px;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="width:34px;height:34px;background:rgba(201,169,98,0.15);border:1px solid rgba(201,169,98,0.35);border-radius:8px;text-align:center;vertical-align:middle;color:#c9a962;font-weight:600;font-size:15px;">H</td>
<td style="padding-left:10px;color:#ffffff;font-size:16px;font-weight:600;">Helm</td>
</tr></table>
<p style="color:#c9a962;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:22px 0 0 0;">You've been added</p>
<h1 style="color:#ffffff;font-size:24px;font-weight:400;margin:10px 0 0 0;line-height:1.3;">{inviter_name} invited you to<br><span style="color:#c9a962;">{workspace_name}</span></h1>
<p style="color:#a1a1aa;font-size:15px;line-height:1.6;margin:18px 0 0 0;">You now have <b style="color:#ffffff;">{role}</b> access to this company's command center on Helm — the CEO Operating System. Sign in with Google to see the morning briefing, decisions, financials and more.</p>
<table cellpadding="0" cellspacing="0" style="margin:28px 0 8px 0;"><tr>
<td style="background:#c9a962;border-radius:8px;">
<a href="{app_url}" style="display:inline-block;padding:12px 26px;color:#09090b;font-size:14px;font-weight:600;text-decoration:none;">Open Helm &rarr;</a>
</td></tr></table>
</td></tr>
<tr><td style="padding:20px 36px 30px 36px;border-top:1px solid rgba(255,255,255,0.06);">
<p style="color:#52525b;font-size:12px;margin:0;line-height:1.6;">Know what matters before your first meeting.<br>If you didn't expect this invite, you can ignore this email.</p>
</td></tr>
</table>
</td></tr></table></body></html>"""


async def send_invite_email(to_email: str, inviter_name: str, workspace_name: str, role: str, app_url: str):
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping invite email to %s", to_email)
        return {"sent": False, "reason": "no_key"}
    resend.api_key = RESEND_API_KEY
    params = {
        "from": SENDER_EMAIL, "to": [to_email],
        "subject": f"{inviter_name} invited you to {workspace_name} on Helm",
        "html": _invite_email_html(inviter_name, workspace_name, role, app_url),
    }
    try:
        email = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "id": (email or {}).get("id")}
    except Exception:
        logger.exception("resend send failed")
        return {"sent": False, "reason": "error"}


# ------------------------- Auth / principal -------------------------
async def _user_from_request(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
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


async def get_ws(workspace_id: str):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


# ------------------------- Activity log -------------------------
def _rel_time(iso: str) -> str:
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except Exception:
        return ""
    secs = (datetime.now(timezone.utc) - t).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


async def log_activity(principal, module, action, summary, patch=None):
    doc = {
        "activity_id": f"act_{uuid.uuid4().hex[:12]}",
        "workspace_id": principal["workspace_id"],
        "actor_user_id": principal["user_id"],
        "actor_name": principal.get("name") or principal.get("email") or "Someone",
        "module": module, "action": action, "summary": summary,
        "patch": patch or {}, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.activities.insert_one(doc)
    return doc


# ------------------------- Financials (computed from entries) -------------------------
def fmt_money(n):
    n = float(n or 0)
    neg = n < 0
    a = abs(n)
    if a >= 1_000_000:
        s = f"${a/1_000_000:.2f}M"
    elif a >= 1_000:
        s = f"${a/1_000:.0f}K"
    else:
        s = f"${a:,.0f}"
    return f"-{s}" if neg else s


async def compute_financials(workspace_id: str):
    from collections import defaultdict
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "financial_settings": 1})
    settings = (ws or {}).get("financial_settings") or {"cash": 0, "gross_margin": None, "currency": "usd"}
    entries = await db.financial_entries.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(5000)
    rev_by, exp_by, rec_by = defaultdict(float), defaultdict(float), defaultdict(float)
    exp_cat = defaultdict(float)
    for e in entries:
        if e["type"] == "revenue":
            rev_by[e["month"]] += e["amount"]
            if e.get("recurring"):
                rec_by[e["month"]] += e["amount"]
        else:
            exp_by[e["month"]] += e["amount"]
            exp_cat[e.get("category") or "Other"] += e["amount"]
    months = sorted(set(list(rev_by) + list(exp_by)))
    last = months[-6:]

    def lbl(m):
        return datetime.strptime(m, "%Y-%m").strftime("%b")

    revenue_series = [{"month": lbl(m), "revenue": round(rev_by[m]), "expenses": round(exp_by[m])} for m in last]
    burn_series = [{"month": lbl(m), "burn": round(exp_by[m] - rev_by[m])} for m in last]
    latest = months[-1] if months else None
    mrr_val = (rec_by[latest] if latest and rec_by[latest] > 0 else (rev_by[latest] if latest else 0))
    cash = settings.get("cash") or 0
    net = [max(exp_by[m] - rev_by[m], 0) for m in months[-3:]]
    avg_burn = sum(net) / len(net) if net else 0
    runway = round(cash / avg_burn, 1) if avg_burn > 0 else None
    burn_val = (exp_by[latest] - rev_by[latest]) if latest else 0
    total_exp = sum(exp_cat.values())
    expense_breakdown = ([{"name": k, "value": round(v / total_exp * 100)} for k, v in sorted(exp_cat.items(), key=lambda x: -x[1])] if total_exp else [])
    gm = settings.get("gross_margin")
    scenarios = []
    if runway:
        scenarios = [
            {"name": "Base", "runway": runway, "desc": "Current net burn held."},
            {"name": "Efficient", "runway": round(cash / (avg_burn * 0.8), 1), "desc": "Trim burn 20%."},
            {"name": "Aggressive Hire", "runway": round(cash / (avg_burn * 1.4), 1), "desc": "Scale spend 40%."},
        ]
    mrr_delta = 0
    if len(revenue_series) >= 2 and revenue_series[-2]["revenue"] > 0:
        mrr_delta = round((revenue_series[-1]["revenue"] - revenue_series[-2]["revenue"]) / revenue_series[-2]["revenue"] * 100, 1)
    return {
        "mrr": fmt_money(mrr_val), "arr": fmt_money(mrr_val * 12), "runway_months": runway,
        "burn": fmt_money(burn_val), "cash": fmt_money(cash),
        "gross_margin": ((f"{int(gm)}%" if float(gm).is_integer() else f"{gm}%") if gm is not None else "—"),
        "revenue_series": revenue_series, "burn_series": burn_series, "scenarios": scenarios,
        "expense_breakdown": expense_breakdown, "settings": settings,
        "mrr_delta": mrr_delta, "spark": [r["revenue"] for r in revenue_series],
        "burn_tone": "negative" if burn_val > 0 else "positive", "has_data": bool(entries),
    }


# ------------------------- Auth routes -------------------------
class SessionInput(BaseModel):
    session_id: str


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


async def _issue_session(response: Response, user_id: str) -> str:
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": expires_at, "created_at": datetime.now(timezone.utc),
    })
    set_session_cookie(response, session_token)
    return session_token


def _auth_redirect_uri(request: Request) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/auth/google/callback"


@api_router.get("/auth/config")
async def auth_config():
    clerk_on = clerk_auth.clerk_configured()
    google_on = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET) and not clerk_on
    provider = "clerk" if clerk_on else ("google" if google_on else "none")
    return {
        "demo_login": False,
        "clerk_enabled": clerk_on,
        "google_oauth": google_on,
        "provider": provider,
        "ai_ready": helm_llm.anthropic_configured(),
    }


@api_router.post("/auth/clerk")
async def clerk_login(request: Request, response: Response):
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="Missing Clerk session token")
    try:
        identity = await clerk_auth.verify_clerk_session_token(token)
    except Exception:
        logger.exception("clerk token verification failed")
        raise HTTPException(status_code=401, detail="Invalid Clerk session")
    user = await _upsert_clerk_user(
        email=identity["email"],
        name=identity.get("name"),
        picture=identity.get("picture"),
        clerk_id=identity["clerk_id"],
    )
    await _issue_session(response, user["user_id"])
    return {"ok": True, "user_id": user["user_id"], "email": user["email"]}


@api_router.post("/auth/session")
async def process_session_removed():
    raise HTTPException(
        status_code=410,
        detail="Emergent session auth is retired. Use Google sign-in via /api/auth/google/login.",
    )


@api_router.post("/auth/demo-login")
async def demo_login_removed():
    raise HTTPException(status_code=410, detail="Demo login is disabled for production.")


@api_router.get("/auth/google/login")
async def google_login(request: Request, redirect: Optional[str] = None):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=400, detail="Google OAuth not configured")
    dest = redirect or (f"{APP_URL}/app" if APP_URL else "/app")
    if not _allowed_auth_redirect(dest):
        raise HTTPException(status_code=400, detail="Invalid redirect URL")
    state = jwt.encode(
        {"redirect": dest, "ts": int(datetime.now(timezone.utc).timestamp())},
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


@api_router.get("/auth/google/callback")
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


@api_router.get("/auth/me")
async def auth_me(user=Depends(get_user)):
    base = {"user_id": user["user_id"], "email": user["email"],
            "name": user.get("name"), "picture": user.get("picture")}
    active = user.get("active_workspace_id")
    membership = None
    if active:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "workspace_id": active, "status": "active"}, {"_id": 0})
    if not membership:
        membership = await db.memberships.find_one(
            {"user_id": user["user_id"], "status": "active"}, {"_id": 0})
        if membership:
            await db.users.update_one({"user_id": user["user_id"]},
                                      {"$set": {"active_workspace_id": membership["workspace_id"]}})
    if not membership:
        return {**base, "workspace_id": None, "needs_workspace": True, "role": None,
                "pack": None, "perms": [], "default_route": "/app/welcome", "pack_label": None}
    pack = pack_of(membership)
    return {**base, "workspace_id": membership["workspace_id"], "needs_workspace": False,
            "role": membership["role"], "pack": pack, "perms": sorted(perms_for(pack)),
            "default_route": PACK_HOME.get(pack, "/app"), "pack_label": PACK_LABEL.get(pack, "Member")}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ------------------------- Workspaces & members -------------------------
@api_router.get("/workspaces")
async def list_workspaces(principal=Depends(get_principal)):
    mems = await db.memberships.find({"user_id": principal["user_id"], "status": "active"}, {"_id": 0}).to_list(50)
    out = []
    for m in mems:
        ws = await db.workspaces.find_one({"workspace_id": m["workspace_id"]}, {"_id": 0, "name": 1, "workspace_id": 1, "plan": 1})
        if ws:
            out.append({"workspace_id": ws["workspace_id"], "name": ws["name"], "plan": ws["plan"],
                        "role": m["role"], "active": ws["workspace_id"] == principal["workspace_id"]})
    return {"workspaces": out}


class SwitchInput(BaseModel):
    workspace_id: str


@api_router.post("/workspaces/switch")
async def switch_workspace(payload: SwitchInput, principal=Depends(get_principal)):
    m = await db.memberships.find_one({"user_id": principal["user_id"], "workspace_id": payload.workspace_id, "status": "active"}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await db.users.update_one({"user_id": principal["user_id"]}, {"$set": {"active_workspace_id": payload.workspace_id}})
    return {"ok": True, "workspace_id": payload.workspace_id}


class CreateWsInput(BaseModel):
    name: str


@api_router.post("/workspaces")
async def create_workspace(payload: CreateWsInput, user=Depends(get_user)):
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    doc = build_workspace(ws_id, payload.name.strip() or "New Company", user["user_id"], empty=True)
    await db.workspaces.insert_one(doc)
    await db.memberships.insert_one({
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
        "user_id": user["user_id"], "email": user["email"], "role": "owner",
        "pack": "owner", "status": "active", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": ws_id}})
    return {"ok": True, "workspace_id": ws_id}


class JoinInput(BaseModel):
    code: str


@api_router.get("/workspaces/join-info")
async def join_info(code: str, user=Depends(get_user)):
    c = code.strip()
    ws = await db.workspaces.find_one({"join_code": c}, {"_id": 0, "name": 1, "workspace_id": 1})
    if not ws:
        ws = await db.workspaces.find_one({"join_code": c.upper()}, {"_id": 0, "name": 1, "workspace_id": 1})
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return {"name": ws["name"], "workspace_id": ws["workspace_id"]}


@api_router.post("/workspaces/join")
async def join_workspace(payload: JoinInput, request: Request, user=Depends(get_user)):
    _check_join_rate_limit(_client_ip(request))
    code = payload.code.strip()
    ws = await db.workspaces.find_one({"join_code": code}, {"_id": 0})
    if not ws:
        ws = await db.workspaces.find_one({"join_code": code.upper()}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    ws_id = ws["workspace_id"]
    existing = await db.memberships.find_one({"workspace_id": ws_id, "user_id": user["user_id"]})
    if not existing:
        await db.memberships.insert_one({
            "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
            "user_id": user["user_id"], "email": user["email"], "role": "member",
            "pack": "member", "status": "active", "created_at": datetime.now(timezone.utc).isoformat(),
        })
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": ws_id}})
    return {"ok": True, "workspace_id": ws_id}


@api_router.get("/workspaces/join-code")
async def get_join_code(principal=Depends(require("members:invite"))):
    ws = await get_ws(principal["workspace_id"])
    code = ws.get("join_code")
    if not code:
        code = gen_join_code()
        await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": {"join_code": code}})
    return {"join_code": code}


@api_router.get("/members")
async def list_members(principal=Depends(get_principal)):
    mems = await db.memberships.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).to_list(100)
    out = []
    for m in mems:
        u = await db.users.find_one({"user_id": m.get("user_id")}, {"_id": 0, "name": 1, "picture": 1}) if m.get("user_id") else None
        out.append({
            "membership_id": m["membership_id"], "email": m["email"], "role": m["role"],
            "pack": pack_of(m), "status": m["status"], "name": (u or {}).get("name"),
            "picture": (u or {}).get("picture"), "user_id": m.get("user_id"),
            "is_self": m.get("user_id") == principal["user_id"],
        })
    return {"members": out, "my_role": principal["role"], "my_pack": principal["pack"]}


class InviteInput(BaseModel):
    email: EmailStr
    pack: str = "member"


@api_router.post("/members/invite")
async def invite_member(payload: InviteInput, request: Request, principal=Depends(require("members:invite"))):
    if payload.pack not in VALID_PACKS:
        raise HTTPException(status_code=400, detail="Unknown access pack")
    pack = payload.pack
    if pack == "owner" and "members:manage" not in perms_for(principal["pack"]):
        raise HTTPException(status_code=403, detail="Only an owner can grant owner access")
    role = "owner" if pack == "owner" else "member"
    email = payload.email.strip().lower()
    existing = await db.memberships.find_one({"workspace_id": principal["workspace_id"], "email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Already a member or invited")
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    await db.memberships.insert_one({
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": principal["workspace_id"],
        "user_id": existing_user["user_id"] if existing_user else None, "email": email,
        "role": role, "pack": pack, "status": "active" if existing_user else "invited",
        "invite_token": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    ws = await get_ws(principal["workspace_id"])
    app_url = APP_URL or FRONTEND_URL or str(request.base_url).rstrip("/")
    email_result = await send_invite_email(email, principal.get("name") or "Your team lead", ws["name"], PACK_LABEL.get(pack, "Member"), app_url)
    return {"ok": True, "auto_joined": bool(existing_user), "email_sent": email_result.get("sent", False)}


class RoleInput(BaseModel):
    pack: str


@api_router.patch("/members/{membership_id}")
async def update_member_role(membership_id: str, payload: RoleInput, principal=Depends(require("members:invite"))):
    m = await db.memberships.find_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.get("user_id") == principal["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own access")
    if payload.pack not in VALID_PACKS:
        raise HTTPException(status_code=400, detail="Unknown access pack")
    is_owner_admin = "members:manage" in perms_for(principal["pack"])
    if (pack_of(m) == "owner" or payload.pack == "owner") and not is_owner_admin:
        raise HTTPException(status_code=403, detail="Only an owner can change owner access")
    pack = payload.pack
    role = "owner" if pack == "owner" else "member"
    await db.memberships.update_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"$set": {"role": role, "pack": pack}})
    return {"ok": True}


@api_router.delete("/members/{membership_id}")
async def remove_member(membership_id: str, principal=Depends(require("members:manage"))):
    m = await db.memberships.find_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.get("user_id") == principal["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    await db.memberships.delete_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]})
    return {"ok": True}


# ------------------------- Company / module data -------------------------
@api_router.get("/company")
async def company(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return {"name": c["name"], "plan": c["plan"], "stage": c["stage"], "employees": c["employees"],
            "founded": c["founded"], "mission": c["mission"], "ceo_name": principal.get("name") or "CEO",
            "role": principal["role"], "workspace_id": c["workspace_id"],
            "onboarding_done": c.get("onboarding_done", True), "template": c.get("template", "sample")}


class TemplateInput(BaseModel):
    template: str  # sample | clean


_PRESERVE_WS_FIELDS = frozenset({
    "join_code", "oauth_session_token_enc", "google_tokens", "quickbooks_tokens",
    "plan", "billing_provider", "paddle_subscription_id", "paddle_customer_id",
    "paddle_last_event_at", "billing_status", "subscription_status", "canceled_at",
    "workspace_id", "owner_user_id", "created_at",
})


@api_router.post("/workspace/apply-template")
async def apply_template(payload: TemplateInput, principal=Depends(require("workspace:edit"))):
    ws_id = principal["workspace_id"]
    if payload.template == "sample":
        current = await get_ws(ws_id)
        fresh = build_workspace(ws_id, current["name"], principal["user_id"], empty=False)
        update = {k: v for k, v in fresh.items() if k not in _PRESERVE_WS_FIELDS}
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": update})
        await db.financial_entries.delete_many({"workspace_id": ws_id})
        await db.financial_entries.insert_many(sample_financial_entries(ws_id))
    else:
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": {"onboarding_done": True}})
    return {"ok": True}


@api_router.get("/briefing")
async def briefing(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    b = dict(c["briefing"])
    is_pro = c["plan"] == "pro"
    fin = await compute_financials(c["workspace_id"])
    metrics = [
        {"label": "MRR", "value": fin["mrr"], "delta": fin["mrr_delta"], "tone": "positive"},
        {"label": "Runway", "value": f"{fin['runway_months']}mo" if fin["runway_months"] else "—", "delta": 0, "tone": "neutral"},
        {"label": "Burn", "value": fin["burn"], "delta": 0, "tone": fin["burn_tone"]},
    ]
    nrr = b.get("nrr")
    if nrr:
        metrics.append({"label": "NRR", "value": nrr["value"], "delta": nrr["delta"], "tone": nrr["tone"]})
    b["metrics"] = metrics
    acts = await db.activities.find({"workspace_id": c["workspace_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5)
    act_items = [{"title": a["summary"], "detail": f"{a['actor_name']} · {_rel_time(a['created_at'])}", "tone": "neutral"} for a in acts]
    b["what_changed"] = act_items + list(b.get("what_changed", []))
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": c["workspace_id"], "day": day}, {"_id": 0}).sort("updated_at", -1).to_list(50)
    b["team_updates"] = [{"user_name": u.get("user_name"), "text": u.get("text"),
                          "blocker": u.get("blocker", False), "mood": u.get("mood"),
                          "ago": _rel_time(u.get("updated_at", ""))} for u in ups]
    return {**b, "is_pro": is_pro, "ai_summary": b.get("ai_summary") if is_pro else None}


@api_router.get("/activities")
async def list_activities(principal=Depends(get_principal)):
    acts = await db.activities.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("created_at", -1).to_list(40)
    for a in acts:
        a["ago"] = _rel_time(a["created_at"])
    return {"activities": acts}


@api_router.post("/briefing/generate")
async def generate_briefing(principal=Depends(require("briefing:generate"))):
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
    b = c["briefing"]
    context = {"company": c["name"], "metrics": b.get("what_to_decide"), "what_changed": b["what_changed"],
               "decisions": b["what_to_decide"], "financials": await compute_financials(c["workspace_id"])}
    system = ("You are Helm, an executive chief-of-staff AI for a startup CEO. Write a crisp morning briefing in 3-4 sentences. "
              "Synthesis over raw data, signal over noise. Lead with what matters most, name the single most important decision, "
              "and end with a confident recommendation. No fluff, no lists.")
    text = await helm_llm.complete(system, f"Company data for today:\n{json.dumps(context, indent=2)}\n\nWrite the CEO's morning briefing.")
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"briefing.ai_summary": text}})
    return {"ai_summary": text}


@api_router.get("/decisions")
async def decisions(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return {"decisions": c["decisions"], "is_pro": c["plan"] == "pro", "can_act": "decisions:act" in perms_for(principal["pack"])}


class DecisionAction(BaseModel):
    action: str
    owner: Optional[str] = None


@api_router.post("/decisions/{decision_id}/action")
async def decision_action(decision_id: str, payload: DecisionAction, principal=Depends(require("decisions:act"))):
    c = await get_ws(principal["workspace_id"])
    decisions = c["decisions"]
    found = False
    for d in decisions:
        if d["id"] == decision_id:
            d["status"] = payload.action
            if payload.owner:
                d["owner"] = payload.owner
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    return {"ok": True, "decisions": decisions}


class DecisionInput(BaseModel):
    title: str
    category: str = "General"
    description: str = ""
    recommendation: Optional[str] = ""
    confidence: Optional[int] = None
    due: str = ""
    impact: str = "Medium"


def _decision_fields(p: "DecisionInput"):
    conf = None if p.confidence is None else max(0, min(100, int(p.confidence)))
    return {"title": p.title.strip(), "category": p.category.strip() or "General",
            "description": p.description.strip(), "recommendation": (p.recommendation or "").strip(),
            "confidence": conf, "due": p.due.strip() or "—",
            "impact": p.impact if p.impact in ("High", "Medium", "Low") else "Medium"}


@api_router.post("/decisions")
async def create_decision(payload: DecisionInput, principal=Depends(require("decisions:act"))):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    d = {"id": f"d_{uuid.uuid4().hex[:8]}", "status": "pending", "owner": None, **_decision_fields(payload)}
    decisions = c["decisions"] + [d]
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    await log_activity(principal, "decisions", "decision.create", f"New decision: {d['title']}")
    return {"ok": True, "decision": d}


@api_router.patch("/decisions/{decision_id}")
async def edit_decision(decision_id: str, payload: DecisionInput, principal=Depends(require("decisions:act"))):
    c = await get_ws(principal["workspace_id"])
    decisions = c["decisions"]
    found = None
    for d in decisions:
        if d["id"] == decision_id:
            d.update(_decision_fields(payload))
            found = d
            break
    if not found:
        raise HTTPException(status_code=404, detail="Decision not found")
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    return {"ok": True}


@api_router.delete("/decisions/{decision_id}")
async def delete_decision(decision_id: str, principal=Depends(require("decisions:act"))):
    c = await get_ws(principal["workspace_id"])
    decisions = [d for d in c["decisions"] if d["id"] != decision_id]
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    return {"ok": True}


@api_router.get("/onboarding/checklist")
async def onboarding_checklist(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    ws = c["workspace_id"]
    has_fin = await db.financial_entries.count_documents({"workspace_id": ws}) > 0
    people_n = len(c["people"]["people"])
    members_n = await db.memberships.count_documents({"workspace_id": ws, "status": "active"})
    day = datetime.now(timezone.utc).date().isoformat()
    has_update = await db.updates.count_documents({"workspace_id": ws, "user_id": principal["user_id"], "day": day}) > 0
    steps = [
        {"id": "financials", "label": "Add your financials", "done": has_fin, "route": "/app/financials"},
        {"id": "people", "label": "Add your team roster", "done": people_n > 0, "route": "/app/people"},
        {"id": "invite", "label": "Invite a teammate", "done": members_n > 1, "route": "/app/members"},
        {"id": "update", "label": "Post your first daily update", "done": has_update, "route": "/app/me"},
    ]
    return {"steps": steps, "complete": all(s["done"] for s in steps)}


# ------------------------- Sales pipeline -------------------------
DEAL_STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
STAGE_PROB = {"lead": 0.1, "qualified": 0.3, "proposal": 0.5, "negotiation": 0.7, "won": 1.0, "lost": 0.0}
STAGE_LABEL = {"lead": "Lead", "qualified": "Qualified", "proposal": "Proposal",
               "negotiation": "Negotiation", "won": "Won", "lost": "Lost"}


def _deal_metrics(deals):
    open_deals = [d for d in deals if d["stage"] not in ("won", "lost")]
    by_stage = [{"stage": s, "label": STAGE_LABEL[s],
                 "count": len([d for d in deals if d["stage"] == s]),
                 "value": round(sum(d["value"] for d in deals if d["stage"] == s), 2)} for s in DEAL_STAGES]
    return {"open_value": round(sum(d["value"] for d in open_deals), 2),
            "weighted_value": round(sum(d["value"] * STAGE_PROB.get(d["stage"], 0) for d in open_deals), 2),
            "won_value": round(sum(d["value"] for d in deals if d["stage"] == "won"), 2),
            "open_count": len(open_deals), "by_stage": by_stage}


class DealInput(BaseModel):
    name: str
    company: str = ""
    value: float = 0
    stage: str = "lead"
    owner_name: str = ""
    close_date: str = ""


@api_router.get("/deals")
async def list_deals(principal=Depends(get_principal)):
    deals = await db.deals.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"deals": deals, "can_write": "sales:write" in perms_for(principal["pack"]),
            "metrics": _deal_metrics(deals), "stages": [{"id": s, "label": STAGE_LABEL[s]} for s in DEAL_STAGES]}


@api_router.post("/deals")
async def create_deal(payload: DealInput, principal=Depends(require("sales:write"))):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Deal name is required")
    stage = payload.stage if payload.stage in DEAL_STAGES else "lead"
    now = datetime.now(timezone.utc).isoformat()
    deal = {"id": f"deal_{uuid.uuid4().hex[:8]}", "workspace_id": principal["workspace_id"],
            "name": payload.name.strip(), "company": payload.company.strip(), "value": round(payload.value, 2),
            "stage": stage, "owner_name": payload.owner_name.strip() or (principal.get("name") or ""),
            "close_date": payload.close_date.strip(), "created_at": now, "updated_at": now}
    await db.deals.insert_one(dict(deal))
    await log_activity(principal, "sales", "deal.create",
                       f"New deal: {deal['name']} · {fmt_money(deal['value'])} ({STAGE_LABEL[stage]})",
                       {"value": deal["value"], "stage": stage})
    return {"ok": True, "deal": deal}


@api_router.patch("/deals/{deal_id}")
async def update_deal(deal_id: str, payload: DealInput, principal=Depends(require("sales:write"))):
    d = await db.deals.find_one({"id": deal_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    stage = payload.stage if payload.stage in DEAL_STAGES else d["stage"]
    upd = {"name": payload.name.strip() or d["name"], "company": payload.company.strip(),
           "value": round(payload.value, 2), "stage": stage,
           "owner_name": payload.owner_name.strip() or d.get("owner_name", ""),
           "close_date": payload.close_date.strip(), "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.deals.update_one({"id": deal_id, "workspace_id": principal["workspace_id"]}, {"$set": upd})
    if stage != d["stage"]:
        if stage == "won":
            summary = f"Won {upd['name']} · {fmt_money(upd['value'])}"
        elif stage == "lost":
            summary = f"Lost {upd['name']}"
        else:
            summary = f"{upd['name']} moved to {STAGE_LABEL[stage]}"
        await log_activity(principal, "sales", "deal.stage", summary, {"stage": stage})
    return {"ok": True}


@api_router.delete("/deals/{deal_id}")
async def delete_deal(deal_id: str, principal=Depends(require("sales:write"))):
    await db.deals.delete_one({"id": deal_id, "workspace_id": principal["workspace_id"]})
    return {"ok": True}


@api_router.get("/telemetry")
async def telemetry(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    fin = await compute_financials(c["workspace_id"])
    items = c["tasks"]["items"]
    open_tasks = len([t for t in items if t.get("column") != "done"])
    headcount = c.get("employees") or len(c["people"]["people"])
    kpis = []
    if fin["has_data"]:
        kpis += [
            {"label": "MRR", "value": fin["mrr"], "delta": fin["mrr_delta"],
             "tone": "positive" if fin["mrr_delta"] >= 0 else "negative", "spark": fin["spark"]},
            {"label": "ARR", "value": fin["arr"], "delta": 0, "tone": "neutral", "spark": fin["spark"]},
            {"label": "Runway", "value": f"{fin['runway_months']}mo" if fin["runway_months"] else "—",
             "delta": 0, "tone": "neutral", "spark": []},
            {"label": "Net Burn", "value": fin["burn"], "delta": 0, "tone": fin["burn_tone"],
             "spark": [b["burn"] for b in fin["burn_series"]]},
        ]
    kpis += [
        {"label": "Headcount", "value": str(headcount), "delta": 0, "tone": "neutral", "spark": []},
        {"label": "Open Tasks", "value": str(open_tasks), "delta": 0, "tone": "neutral", "spark": []},
    ]
    deals = await db.deals.find({"workspace_id": c["workspace_id"]}, {"_id": 0}).to_list(500)
    if deals:
        kpis.append({"label": "Pipeline", "value": fmt_money(_deal_metrics(deals)["open_value"]),
                     "delta": 0, "tone": "neutral", "spark": []})
    revenue_trend = [{"month": r["month"], "mrr": r["revenue"], "target": round(r["revenue"] * 1.03)}
                     for r in fin["revenue_series"]]
    tel = c.get("telemetry") or {}
    return {"kpis": kpis, "revenue_trend": revenue_trend,
            "funnel": tel.get("funnel") or [], "risks": tel.get("risks") or [],
            "expense_breakdown": fin["expense_breakdown"]}


@api_router.get("/financials")
async def financials(principal=Depends(get_principal)):
    fin = await compute_financials(principal["workspace_id"])
    entries = await db.financial_entries.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("month", -1).to_list(5000)
    return {**fin, "entries": entries, "can_write": "finance:write" in perms_for(principal["pack"]),
            "can_manage": "integrations:manage" in perms_for(principal["pack"])}


class FinEntryInput(BaseModel):
    type: str
    category: str
    amount: float
    month: str
    recurring: bool = False
    note: Optional[str] = ""


@api_router.post("/financials/entries")
async def add_fin_entry(payload: FinEntryInput, principal=Depends(require("finance:write"))):
    if payload.type not in ("revenue", "expense"):
        raise HTTPException(status_code=400, detail="type must be revenue or expense")
    entry = {"id": f"fe_{uuid.uuid4().hex[:10]}", "workspace_id": principal["workspace_id"],
             "type": payload.type, "category": payload.category.strip() or "Other",
             "amount": round(payload.amount, 2), "month": payload.month, "recurring": payload.recurring,
             "note": (payload.note or "").strip(), "source": "manual", "created_by": principal["user_id"],
             "created_at": datetime.now(timezone.utc).isoformat()}
    await db.financial_entries.insert_one(entry)
    entry.pop("_id", None)
    await log_activity(principal, "financials", "entry.add",
                       f"Logged {payload.type} · {entry['category']} {fmt_money(entry['amount'])} ({payload.month})",
                       {"type": payload.type, "amount": entry["amount"], "month": payload.month})
    return {"ok": True, "entry": entry}


@api_router.patch("/financials/entries/{entry_id}")
async def edit_fin_entry(entry_id: str, payload: FinEntryInput, principal=Depends(require("finance:write"))):
    res = await db.financial_entries.update_one(
        {"id": entry_id, "workspace_id": principal["workspace_id"]},
        {"$set": {"type": payload.type, "category": payload.category.strip() or "Other",
                  "amount": round(payload.amount, 2), "month": payload.month,
                  "recurring": payload.recurring, "note": (payload.note or "").strip()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    await log_activity(principal, "financials", "entry.edit",
                       f"Updated a {payload.type} entry · {payload.category.strip() or 'Other'} ({payload.month})")
    return {"ok": True}


@api_router.delete("/financials/entries/{entry_id}")
async def delete_fin_entry(entry_id: str, principal=Depends(require("finance:write"))):
    doc = await db.financial_entries.find_one({"id": entry_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    await db.financial_entries.delete_one({"id": entry_id, "workspace_id": principal["workspace_id"]})
    if doc:
        await log_activity(principal, "financials", "entry.delete",
                           f"Removed a {doc.get('type')} entry · {doc.get('category')} ({doc.get('month')})")
    return {"ok": True}


class FinSettingsInput(BaseModel):
    cash: float
    gross_margin: Optional[float] = None


@api_router.put("/financials/settings")
async def update_fin_settings(payload: FinSettingsInput, principal=Depends(require("finance:write"))):
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]},
                                   {"$set": {"financial_settings.cash": round(payload.cash, 2),
                                             "financial_settings.gross_margin": payload.gross_margin}})
    fin = await compute_financials(principal["workspace_id"])
    runway = fin["runway_months"]
    await log_activity(principal, "financials", "settings.update",
                       f"Updated cash to {fmt_money(payload.cash)}" + (f" — runway now {runway}mo" if runway else ""),
                       {"cash": payload.cash, "runway_months": runway})
    return {"ok": True}


@api_router.get("/tasks")
async def tasks(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    t = dict(c["tasks"])
    t["can_create"] = "tasks:create" in perms_for(principal["pack"])
    t["can_assign"] = "tasks:assign" in perms_for(principal["pack"])
    t["my_user_id"] = principal["user_id"]
    return t


@api_router.get("/tasks/me")
async def my_tasks(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    items = [t for t in c["tasks"]["items"] if t.get("assignee_user_id") == principal["user_id"]]
    return {"items": items, "columns": c["tasks"]["columns"]}


class TaskInput(BaseModel):
    title: str
    priority: str = "Medium"
    tag: str = "General"
    due: str = ""
    column: str = "backlog"
    assignee_user_id: Optional[str] = None


@api_router.post("/tasks")
async def create_task(payload: TaskInput, principal=Depends(require("tasks:create"))):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    t = c["tasks"]
    assignee_uid = principal["user_id"]
    assignee_name = principal.get("name") or principal.get("email") or "Me"
    if payload.assignee_user_id and payload.assignee_user_id != principal["user_id"]:
        if "tasks:assign" not in perms_for(principal["pack"]):
            raise HTTPException(status_code=403, detail="You can only create tasks for yourself")
        member = await db.memberships.find_one({"workspace_id": principal["workspace_id"], "user_id": payload.assignee_user_id, "status": "active"}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Assignee is not in this workspace")
        u = await db.users.find_one({"user_id": payload.assignee_user_id}, {"_id": 0, "name": 1})
        assignee_uid = payload.assignee_user_id
        assignee_name = (u or {}).get("name") or member["email"]
    item = {"id": f"t_{uuid.uuid4().hex[:8]}", "title": payload.title.strip(),
            "assignee": assignee_name, "assignee_user_id": assignee_uid,
            "priority": payload.priority if payload.priority in ("High", "Medium", "Low") else "Medium",
            "column": payload.column or "backlog", "tag": (payload.tag or "General").strip(),
            "due": (payload.due or "").strip(), "progress": 0}
    t["items"].append(item)
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"tasks": t}})
    return {"ok": True, "task": item}


class TaskMove(BaseModel):
    column: str


@api_router.patch("/tasks/{task_id}")
async def move_task(task_id: str, payload: TaskMove, principal=Depends(require("tasks:move"))):
    c = await get_ws(principal["workspace_id"])
    t = c["tasks"]
    target = next((i for i in t["items"] if i["id"] == task_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Task not found")
    owns = target.get("assignee_user_id") == principal["user_id"]
    if target.get("assignee_user_id") and not owns and "tasks:assign" not in perms_for(principal["pack"]):
        raise HTTPException(status_code=403, detail="You can only move your own tasks")
    target["column"] = payload.column
    if payload.column == "done":
        target["progress"] = 100
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"tasks": t}})
    return {"ok": True}


# ------------------------- Daily updates -------------------------
class UpdateInput(BaseModel):
    text: str
    blocker: bool = False
    mood: Optional[str] = None


@api_router.get("/updates/me")
async def my_update(principal=Depends(get_principal)):
    day = datetime.now(timezone.utc).date().isoformat()
    u = await db.updates.find_one({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "day": day}, {"_id": 0})
    return {"update": u, "day": day}


@api_router.get("/updates/today")
async def todays_updates(principal=Depends(get_principal)):
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": principal["workspace_id"], "day": day}, {"_id": 0}).sort("updated_at", -1).to_list(50)
    for u in ups:
        u["ago"] = _rel_time(u.get("updated_at", ""))
    return {"updates": ups, "day": day}


@api_router.post("/updates")
async def post_update(payload: UpdateInput, principal=Depends(require("updates:write"))):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Update text is required")
    day = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    text = payload.text.strip()[:600]
    name = principal.get("name") or principal.get("email") or "Someone"
    summary = f'Update from {name}: "{text[:90]}"' + (" — blocked" if payload.blocker else "")
    existing = await db.updates.find_one({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "day": day}, {"_id": 0})
    if existing:
        await db.updates.update_one({"update_id": existing["update_id"]},
                                    {"$set": {"text": text, "blocker": payload.blocker, "mood": payload.mood, "updated_at": now}})
        if existing.get("activity_id"):
            await db.activities.update_one({"activity_id": existing["activity_id"]}, {"$set": {"summary": summary, "created_at": now}})
        return {"ok": True, "edited": True}
    act = await log_activity(principal, "updates", "daily.update", summary, {"blocker": payload.blocker})
    doc = {"update_id": f"upd_{uuid.uuid4().hex[:10]}", "workspace_id": principal["workspace_id"],
           "user_id": principal["user_id"], "user_name": name, "day": day, "text": text,
           "blocker": payload.blocker, "mood": payload.mood, "activity_id": act["activity_id"],
           "created_at": now, "updated_at": now}
    await db.updates.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "edited": False, "update": doc}


@api_router.get("/reports")
async def reports(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    fin = await compute_financials(c["workspace_id"])
    items = c["tasks"]["items"]
    done = len([t for t in items if t.get("column") == "done"])
    inprog = len([t for t in items if t.get("column") == "in_progress"])
    openc = len([t for t in items if t.get("column") != "done"])
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": c["workspace_id"], "day": day}, {"_id": 0}).to_list(200)
    blocked = len([u for u in ups if u.get("blocker")])
    headcount = c.get("employees") or len(c["people"]["people"])
    reports = [
        {"id": "fin", "title": "Financial Snapshot", "type": "Finance", "period": "Live",
         "summary": f"MRR {fin['mrr']} · ARR {fin['arr']} · runway {fin['runway_months'] or '—'}mo · net burn {fin['burn']}.",
         "metrics": [{"label": "MRR", "value": fin["mrr"]},
                     {"label": "Runway", "value": f"{fin['runway_months']}mo" if fin["runway_months"] else "—"},
                     {"label": "Burn", "value": fin["burn"]}]},
        {"id": "team", "title": "Team Pulse", "type": "People", "period": "Today",
         "summary": f"{headcount} people · {len(ups)} daily update(s) today · {blocked} blocked.",
         "metrics": [{"label": "Headcount", "value": str(headcount)},
                     {"label": "Updates", "value": str(len(ups))},
                     {"label": "Blocked", "value": str(blocked)}]},
        {"id": "exec", "title": "Execution", "type": "Delivery", "period": "Live",
         "summary": f"{done} shipped · {inprog} in progress · {openc} open across the board.",
         "metrics": [{"label": "Shipped", "value": str(done)},
                     {"label": "In progress", "value": str(inprog)},
                     {"label": "Open", "value": str(openc)}]},
    ]
    return {"reports": reports, "is_pro": c["plan"] == "pro"}


@api_router.post("/reports/weekly-pack")
async def weekly_pack(principal=Depends(require("reports:pack"))):
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
    context = {"company": c["name"], "financials": await compute_financials(c["workspace_id"]),
               "kpis": c["telemetry"]["kpis"], "reports": [{"title": r["title"], "summary": r["summary"]} for r in c["reports"]]}
    system = ("You are Helm, writing the Weekly CEO Pack. Produce a board-ready weekly summary in markdown with sections: "
              "Headline, Growth, Financial Health, Risks, and This Week's Focus. Be concise, executive, and specific.")
    text = await helm_llm.complete(system, f"Data:\n{json.dumps(context, indent=2)}\n\nWrite the Weekly CEO Pack.")
    return {"content": text}


@api_router.get("/team")
async def team(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    mems = await db.memberships.find({"workspace_id": c["workspace_id"], "status": "active"}, {"_id": 0}).to_list(200)
    day = datetime.now(timezone.utc).date().isoformat()
    ups = {u["user_id"]: u for u in await db.updates.find({"workspace_id": c["workspace_id"], "day": day}, {"_id": 0}).to_list(200)}
    items = c["tasks"]["items"]
    members, total, overloaded = [], 0, 0
    for m in mems:
        uid = m.get("user_id")
        u = await db.users.find_one({"user_id": uid}, {"_id": 0, "name": 1}) if uid else None
        name = (u or {}).get("name") or m["email"]
        open_t = len([t for t in items if t.get("assignee_user_id") == uid and t.get("column") != "done"])
        util = min(open_t * 25, 130)
        status = ("overloaded" if util >= 100 else "high" if util >= 70 else "healthy" if util >= 30 else "available")
        if util >= 100:
            overloaded += 1
        total += util
        upd = ups.get(uid)
        members.append({"name": name, "role": PACK_LABEL.get(pack_of(m), "Member"), "utilization": util,
                        "status": status, "open_tasks": open_t,
                        "posted_today": bool(upd), "blocked": bool(upd and upd.get("blocker"))})
    avg = round(total / len(members)) if members else 0
    return {"members": members, "avg_utilization": avg, "overloaded_count": overloaded}


@api_router.get("/calendar")
async def calendar(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    data = dict(c["calendar"])
    data["live"] = bool(c.get("google_tokens"))
    # Upcoming deadlines from decisions that carry a real (YYYY-MM-DD) due date.
    upcoming = []
    for d in c.get("decisions", []):
        due = (d.get("due") or "").strip()
        try:
            datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            continue
        if d.get("status") == "pending":
            upcoming.append({"id": d["id"], "title": d["title"], "date": due,
                             "type": "Decision", "meta": d.get("category", "")})
    for t in c["tasks"]["items"]:
        due = (t.get("due") or "").strip()
        try:
            datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            continue
        if t.get("column") != "done" and (not t.get("assignee_user_id") or t.get("assignee_user_id") == principal["user_id"]):
            upcoming.append({"id": t["id"], "title": t["title"], "date": due,
                             "type": "Task", "meta": t.get("tag", "")})
    upcoming.sort(key=lambda x: x["date"])
    data["upcoming"] = upcoming
    return data


@api_router.get("/people")
async def people(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    data = dict(c["people"])
    data["can_write"] = "people:write" in perms_for(principal["pack"])
    return data


def _avg_trust(people_list):
    scores = [p.get("trust_score", 0) for p in people_list if isinstance(p.get("trust_score"), (int, float))]
    return round(sum(scores) / len(scores)) if scores else 0


class PersonInput(BaseModel):
    name: str
    role: str = ""
    department: str = ""
    trust_score: int = 80
    quality: str = "B+"
    tasks_done: int = 0
    tenure: str = ""


def _person_fields(payload: PersonInput):
    return {"name": payload.name.strip(), "role": payload.role.strip(),
            "department": payload.department.strip() or "General",
            "trust_score": payload.trust_score, "quality": payload.quality,
            "tasks_done": payload.tasks_done, "tenure": payload.tenure.strip() or "New"}


@api_router.post("/people")
async def add_person(payload: PersonInput, principal=Depends(require("people:write"))):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    c = await get_ws(principal["workspace_id"])
    people = c["people"]
    person = {"id": f"p_{uuid.uuid4().hex[:8]}", **_person_fields(payload)}
    people["people"].append(person)
    people["avg_trust"] = _avg_trust(people["people"])
    headcount = len(people["people"])
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]},
                                   {"$set": {"people": people, "employees": headcount}})
    await log_activity(principal, "people", "person.add",
                       f"Added {person['name']}" + (f" · {person['role']}" if person['role'] else "") + f" — headcount now {headcount}",
                       {"headcount": headcount})
    return {"ok": True, "person": person}


@api_router.patch("/people/{person_id}")
async def edit_person(person_id: str, payload: PersonInput, principal=Depends(require("people:write"))):
    c = await get_ws(principal["workspace_id"])
    people = c["people"]
    found = None
    for p in people["people"]:
        if p["id"] == person_id:
            p.update(_person_fields(payload))
            found = p
            break
    if not found:
        raise HTTPException(status_code=404, detail="Person not found")
    people["avg_trust"] = _avg_trust(people["people"])
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"people": people}})
    await log_activity(principal, "people", "person.edit", f"Updated {found['name']}'s profile")
    return {"ok": True}


@api_router.delete("/people/{person_id}")
async def remove_person(person_id: str, principal=Depends(require("people:write"))):
    c = await get_ws(principal["workspace_id"])
    people = c["people"]
    person = next((p for p in people["people"] if p["id"] == person_id), None)
    people["people"] = [p for p in people["people"] if p["id"] != person_id]
    people["avg_trust"] = _avg_trust(people["people"])
    headcount = len(people["people"])
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]},
                                   {"$set": {"people": people, "employees": headcount}})
    if person:
        await log_activity(principal, "people", "person.delete",
                           f"Removed {person['name']} — headcount now {headcount}", {"headcount": headcount})
    return {"ok": True}


# ------------------------- Ask Helm -------------------------
class AskInput(BaseModel):
    message: str


@api_router.get("/ask/history")
async def ask_history(principal=Depends(get_principal)):
    msgs = await db.chat_messages.find({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


@api_router.post("/ask")
async def ask_helm(payload: AskInput, principal=Depends(require("ask:use"))):
    c = await get_ws(principal["workspace_id"])
    is_pro = c["plan"] == "pro"
    if not is_pro:
        today = datetime.now(timezone.utc).date().isoformat()
        count = await db.chat_messages.count_documents({"workspace_id": c["workspace_id"], "user_id": principal["user_id"], "role": "user", "day": today})
        if count >= 5:
            raise HTTPException(status_code=402, detail="Free plan limited to 5 messages/day. Upgrade to Pro for unlimited.")
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
    now = datetime.now(timezone.utc)
    await db.chat_messages.insert_one({"workspace_id": c["workspace_id"], "user_id": principal["user_id"], "role": "user", "content": payload.message, "created_at": now.isoformat(), "day": now.date().isoformat()})
    context = {"company": c["name"], "stage": c["stage"], "employees": c["employees"],
               "financials": await compute_financials(c["workspace_id"]),
               "kpis": c["telemetry"]["kpis"], "open_decisions": [d["title"] for d in c["decisions"] if d["status"] == "pending"], "risks": c["telemetry"]["risks"]}
    system = (
        f"You are Helm, the CEO's executive AI chief-of-staff for {c['name']} "
        f"(a {c['stage']} startup, {c['employees']} people). Answer like a sharp, trusted operator: "
        f"direct, quantified, decisive. Use the live company data provided. Synthesis over raw data, "
        f"signal over noise. Keep answers tight. Current company snapshot:\n{json.dumps(context, indent=2)}"
    )

    async def gen():
        collected = ""
        try:
            async for chunk in helm_llm.stream_text(system, payload.message):
                collected += chunk
                yield chunk
        except Exception:
            logger.exception("chat stream error")
            if not collected:
                collected = "I hit an error reaching my reasoning engine. Please try again."
                yield collected
        finally:
            await db.chat_messages.insert_one({"workspace_id": c["workspace_id"], "user_id": principal["user_id"], "role": "assistant", "content": collected, "created_at": datetime.now(timezone.utc).isoformat(), "day": datetime.now(timezone.utc).date().isoformat()})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


api_router.add_api_route("/ai/ask-helm", ask_helm, methods=["POST"])
api_router.add_api_route("/ai/ask-kalun", ask_helm, methods=["POST"])


# ------------------------- Integrations -------------------------
GOOGLE_SCOPES = [
    "openid", "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _provider_config(provider: str, base_url: str):
    redirect = f"{base_url}api/oauth/{provider}/callback"
    if provider == "google":
        return {
            "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect, "scope": " ".join(GOOGLE_SCOPES),
            "extra": {"access_type": "offline", "prompt": "consent"},
            "token_field": "google_tokens",
        }
    if provider == "quickbooks":
        return {
            "configured": bool(QB_CLIENT_ID and QB_CLIENT_SECRET),
            "auth_uri": "https://appcenter.intuit.com/connect/oauth2",
            "token_uri": "https://oauth2.platform.intuit.com/oauth2/v1/tokens/bearer",
            "client_id": QB_CLIENT_ID, "client_secret": QB_CLIENT_SECRET,
            "redirect_uri": redirect, "scope": "com.intuit.quickbooks.accounting",
            "extra": {}, "token_field": "quickbooks_tokens",
        }
    return None


@api_router.get("/integrations")
async def integrations(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    ints = []
    for i in c["integrations"]:
        item = dict(i)
        if i.get("provider") == "google":
            item["connected"] = bool(c.get("google_tokens"))
            item["configured"] = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
        elif i.get("provider") == "quickbooks":
            item["connected"] = bool(c.get("quickbooks_tokens"))
            item["configured"] = bool(QB_CLIENT_ID and QB_CLIENT_SECRET)
        else:
            item["configured"] = True
        ints.append(item)
    return {"integrations": ints, "is_pro": c["plan"] == "pro", "can_manage": "integrations:manage" in perms_for(principal["pack"])}


@api_router.post("/integrations/{integration_id}/toggle")
async def toggle_integration(integration_id: str, principal=Depends(require("integrations:manage"))):
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required for live integrations")
    ints = c["integrations"]
    for i in ints:
        if i["id"] == integration_id:
            if i.get("oauth"):
                raise HTTPException(status_code=400, detail="Use Connect to link this provider via OAuth")
            i["connected"] = not i["connected"]
            break
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"integrations": ints}})
    return {"ok": True, "integrations": ints}


@api_router.get("/integrations/{provider}/connect")
async def integration_connect(provider: str, request: Request, principal=Depends(require("integrations:manage"))):
    cfg = _provider_config(provider, str(request.base_url))
    if not cfg:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not cfg["configured"]:
        return {"configured": False, "message": f"{provider.title()} OAuth credentials are not set yet. Add them in the backend .env to enable live connection."}
    params = {"client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "response_type": "code",
              "scope": cfg["scope"], "state": _sign_state(provider, principal["workspace_id"]), **cfg.get("extra", {})}
    return {"configured": True, "authorization_url": f"{cfg['auth_uri']}?{urlencode(params)}"}


@api_router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, realmId: Optional[str] = None):
    cfg = _provider_config(provider, str(request.base_url))
    frontend = str(request.base_url).rstrip("/")
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


@api_router.post("/integrations/{provider}/disconnect")
async def integration_disconnect(provider: str, principal=Depends(require("integrations:manage"))):
    field = "google_tokens" if provider == "google" else "quickbooks_tokens" if provider == "quickbooks" else None
    if not field:
        raise HTTPException(status_code=404, detail="Unknown provider")
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": {field: None}})
    return {"ok": True}


@api_router.get("/integrations/google/calendar-events")
async def google_calendar_events(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    tokens = c.get("google_tokens")
    if not tokens:
        raise HTTPException(status_code=400, detail="Google not connected")
    token = tokens.get("access_token")
    async with httpx.AsyncClient() as hc:
        r = await hc.get("https://www.googleapis.com/calendar/v3/calendars/primary/events",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"timeMin": datetime.now(timezone.utc).isoformat(), "maxResults": 20, "singleEvents": True, "orderBy": "startTime"})
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="Google token expired — reconnect")
    return {"events": r.json().get("items", [])}


# ------------------------- Payments -------------------------
async def get_billing_status(workspace_id: str, pack: str):
    c = await get_ws(workspace_id)
    sub_status = c.get("subscription_status") or c.get("billing_status")
    has_customer = bool(c.get("paddle_customer_id"))
    return {
        "current_plan": c["plan"],
        "pro_price": PRO_PRICE,
        "price": PRO_PRICE,
        "can_manage": "billing:manage" in perms_for(pack),
        "paddle_ready": bool(PADDLE_CLIENT_TOKEN and PADDLE_PRICE_ID),
        "subscription_status": sub_status,
        "billing_provider": c.get("billing_provider"),
        "portal_available": has_customer and bool(PADDLE_API_KEY),
        "demo_reset_enabled": DEMO_RESET_ENABLED,
        "canceled_at": c.get("canceled_at"),
    }


@api_router.get("/billing/plans")
async def billing_plans(principal=Depends(get_principal)):
    return await get_billing_status(principal["workspace_id"], principal["pack"])


@api_router.get("/billing/status")
async def billing_status(principal=Depends(get_principal)):
    return await get_billing_status(principal["workspace_id"], principal["pack"])


@api_router.post("/demo/reset-plan")
async def reset_plan(principal=Depends(require("billing:manage"))):
    if not DEMO_RESET_ENABLED:
        raise HTTPException(status_code=403, detail="Demo reset is disabled")
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {
        "$set": {"plan": "free", "subscription_status": None, "billing_status": None},
        "$unset": {"paddle_subscription_id": "", "paddle_customer_id": ""},
    })
    return {"ok": True}


# ------------------------- Paddle Billing -------------------------
def _verify_paddle_signature(raw: bytes, signature: str) -> bool:
    """Verify Paddle-Signature (ts=<unix>;h1=<hex>[;h1=...]) over `ts:<raw body>`."""
    if not signature or not PADDLE_WEBHOOK_SECRET:
        return False
    parts = {}
    for part in signature.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            parts.setdefault(k, []).append(v)
    ts = (parts.get("ts") or [None])[0]
    h1s = parts.get("h1") or []
    if not ts or not h1s:
        return False
    try:
        if abs(datetime.now(timezone.utc).timestamp() - int(ts)) > 300:
            return False
    except ValueError:
        return False
    signed = f"{ts}:".encode() + raw
    expected = hmac.new(PADDLE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, h) for h in h1s)


@api_router.post("/billing/paddle/config")
async def paddle_config(principal=Depends(require("billing:manage"))):
    if not (PADDLE_CLIENT_TOKEN and PADDLE_PRICE_ID):
        raise HTTPException(status_code=400, detail="Paddle is not configured")
    nonce = uuid.uuid4().hex
    await db.paddle_intents.insert_one({
        "_id": nonce, "workspace_id": principal["workspace_id"], "user_id": principal["user_id"],
        "price_id": PADDLE_PRICE_ID, "used": False, "created_at": datetime.now(timezone.utc),
    })
    return {"client_token": PADDLE_CLIENT_TOKEN, "price_id": PADDLE_PRICE_ID,
            "environment": PADDLE_ENV, "checkout_nonce": nonce,
            "workspace_id": principal["workspace_id"], "user_id": principal["user_id"],
            "email": principal.get("email")}


async def _paddle_provision(event):
    data = event.get("data") or {}
    custom = data.get("custom_data") or {}
    nonce = custom.get("checkout_nonce")
    workspace_id = custom.get("workspace_id")
    user_id = custom.get("user_id")
    if not (nonce and workspace_id and user_id):
        return
    intent = await db.paddle_intents.find_one({"_id": nonce})
    if not intent or intent.get("workspace_id") != workspace_id or intent.get("user_id") != user_id:
        return
    await db.workspaces.update_one({"workspace_id": workspace_id}, {"$set": {
        "plan": "pro", "billing_provider": "paddle",
        "paddle_subscription_id": data.get("subscription_id") or data.get("id"),
        "paddle_customer_id": data.get("customer_id"),
        "paddle_last_event_at": event.get("occurred_at"),
        "subscription_status": "active", "billing_status": "active",
    }, "$unset": {"canceled_at": ""}})
    await db.paddle_intents.update_one({"_id": nonce}, {"$set": {"used": True}})


async def _paddle_downgrade(event, status: str):
    data = event.get("data") or {}
    sub_id = data.get("id")
    filt = {"paddle_subscription_id": sub_id} if sub_id else {}
    if not filt:
        return
    now = event.get("occurred_at") or datetime.now(timezone.utc).isoformat()
    if status in ("canceled", "cancelled"):
        await db.workspaces.update_one(filt, {
            "$set": {
                "plan": "free", "subscription_status": status, "billing_status": status,
                "canceled_at": now, "paddle_last_event_at": now,
            },
            "$unset": {"paddle_subscription_id": ""},
        })
    else:
        await db.workspaces.update_one(filt, {
            "$set": {"subscription_status": status, "billing_status": status, "paddle_last_event_at": now},
        })


@api_router.post("/payments/paddle/portal")
async def paddle_portal(principal=Depends(require("billing:manage"))):
    c = await get_ws(principal["workspace_id"])
    customer_id = c.get("paddle_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Subscribe first to manage billing")
    if not PADDLE_API_KEY:
        raise HTTPException(status_code=400, detail="Paddle is not configured")
    body = {}
    if c.get("paddle_subscription_id"):
        body["subscription_ids"] = [c["paddle_subscription_id"]]
    try:
        async with httpx.AsyncClient() as hc:
            r = await hc.post(
                f"{PADDLE_API_BASE}/customers/{customer_id}/portal-sessions",
                headers={"Authorization": f"Bearer {PADDLE_API_KEY}", "Content-Type": "application/json"},
                json=body,
            )
        if r.status_code >= 400:
            logger.error("paddle portal error: %s", r.text[:500])
            raise HTTPException(status_code=502, detail="Could not open billing portal")
        payload = r.json().get("data") or {}
        url = (payload.get("urls") or {}).get("general", {}).get("overview")
        if not url:
            raise HTTPException(status_code=502, detail="Portal URL not returned")
        return {"url": url}
    except HTTPException:
        raise
    except Exception:
        logger.exception("paddle portal failed")
        raise HTTPException(status_code=502, detail="Could not open billing portal")


@api_router.post("/webhook/paddle")
async def paddle_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("Paddle-Signature", "")
    if not raw or not _verify_paddle_signature(raw, sig):
        raise HTTPException(status_code=400, detail="Invalid Paddle signature")
    event = json.loads(raw)
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event_id")
    try:
        await db.paddle_events.insert_one({"_id": event_id, "type": event_type, "received_at": datetime.now(timezone.utc)})
    except Exception as e:
        if "e11000" in str(e).lower() or "duplicate key" in str(e).lower():
            return {"received": True}
        raise
    if event_type == "transaction.completed":
        await _paddle_provision(event)
    elif event_type in ("subscription.created", "subscription.activated", "subscription.updated"):
        if (event.get("data") or {}).get("status") == "active":
            await _paddle_provision(event)
    elif event_type in ("subscription.canceled", "subscription.cancelled"):
        await _paddle_downgrade(event, "canceled")
    elif event_type == "subscription.paused":
        await _paddle_downgrade(event, "paused")
    elif event_type in ("subscription.past_due", "subscription.past-due"):
        await _paddle_downgrade(event, "past_due")
    return {"received": True}


# ------------------------- GDPR / account -------------------------
_WORKSPACE_COLLECTIONS = (
    "financial_entries", "deals", "activities", "updates", "chat_messages",
    "paddle_intents", "payment_transactions",
)


def _strip_sensitive(doc: dict) -> dict:
    if not doc:
        return doc
    out = {k: v for k, v in doc.items() if k not in (
        "password", "password_hash", "oauth_session_token_enc",
        "google_tokens", "quickbooks_tokens",
    )}
    return out


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


@api_router.get("/account/export")
async def export_account(user=Depends(get_user)):
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    payload = {"user": _strip_sensitive(user_doc), "memberships": memberships}
    admin_ws = [
        m["workspace_id"] for m in memberships
        if m.get("status") == "active" and (m.get("role") == "owner" or pack_of(m) == "owner")
    ]
    if admin_ws:
        workspaces = []
        for ws_id in admin_ws:
            ws = await db.workspaces.find_one({"workspace_id": ws_id}, {"_id": 0})
            if ws:
                workspaces.append(_strip_sensitive(ws))
        payload["workspaces"] = workspaces
    return payload


@api_router.delete("/account")
async def delete_account(user=Depends(get_user)):
    memberships = await db.memberships.find(
        {"user_id": user["user_id"], "status": "active"}, {"_id": 0}).to_list(50)
    owned = [m for m in memberships if m.get("role") == "owner" or pack_of(m) == "owner"]
    sole_owner = []
    for m in owned:
        others = await db.memberships.find(
            {"workspace_id": m["workspace_id"], "status": "active", "user_id": {"$ne": user["user_id"]}},
            {"_id": 0},
        ).to_list(50)
        other_owners = [o for o in others if o.get("role") == "owner" or pack_of(o) == "owner"]
        if not other_owners:
            sole_owner.append(m["workspace_id"])
    if sole_owner:
        raise HTTPException(
            status_code=400,
            detail="Transfer or delete workspace first",
        )
    await db.memberships.delete_many({"user_id": user["user_id"]})
    await db.user_sessions.delete_many({"user_id": user["user_id"]})
    await db.chat_messages.delete_many({"user_id": user["user_id"]})
    await db.updates.delete_many({"user_id": user["user_id"]})
    await db.users.delete_one({"user_id": user["user_id"]})
    return {"ok": True}


async def _delete_workspace_data(ws_id: str):
    for coll in _WORKSPACE_COLLECTIONS:
        await db[coll].delete_many({"workspace_id": ws_id})
    await db.memberships.delete_many({"workspace_id": ws_id})
    await db.workspaces.delete_one({"workspace_id": ws_id})


async def _delete_workspace_handler(principal: dict):
    membership = await db.memberships.find_one(
        {"user_id": principal["user_id"], "workspace_id": principal["workspace_id"], "status": "active"},
        {"_id": 0},
    )
    if not membership or (membership.get("role") != "owner" and pack_of(membership) != "owner"):
        raise HTTPException(status_code=403, detail="Only workspace owners can delete the workspace")
    await _delete_workspace_data(principal["workspace_id"])
    return {"ok": True}


@api_router.delete("/workspace")
async def delete_workspace(principal=Depends(require("billing:manage"))):
    return await _delete_workspace_handler(principal)


@api_router.delete("/workspaces/current")
async def delete_workspace_current(principal=Depends(require("billing:manage"))):
    return await _delete_workspace_handler(principal)


@api_router.get("/health")
async def health():
    """Liveness probe for Render — must return 200 within 5s even when Mongo is down."""
    mongo_ok = False
    try:
        await asyncio.wait_for(db.command("ping", maxTimeMS=500), timeout=1.0)
        mongo_ok = True
    except Exception:
        pass
    return {"status": "ok", "mongo": mongo_ok}


@api_router.get("/")
async def root():
    return {"service": "Helm CEO Operating System"}


@app.get("/")
async def api_root():
    """Friendly response when someone opens the Render host directly (API-only)."""
    return {
        "service": "Helm CEO Operating System API",
        "message": "This URL is the API backend. Open your Vercel app to use Helm.",
        "health": "/api/health",
        "auth": "/api/auth/config",
        "frontend": FRONTEND_URL or None,
    }


app.include_router(api_router)

_cors_origins = CORS_ORIGINS or ([FRONTEND_URL] if FRONTEND_URL else ["http://localhost:3000"])
_cors_regex = CORS_ORIGIN_REGEX
if not _cors_regex and any("emergentagent.com" in o for o in _cors_origins):
    _cors_regex = r"https://.*\.emergentagent\.com"
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _ensure_indexes():
    specs = [
        (db.users, [("email", 1)], {"unique": True}),
        (db.users, [("google_sub", 1)], {"unique": True, "sparse": True}),
        (db.users, [("clerk_id", 1)], {"unique": True, "sparse": True}),
        (db.memberships, [("user_id", 1), ("workspace_id", 1)], {}),
        (db.memberships, [("email", 1), ("status", 1)], {}),
        (db.workspaces, [("workspace_id", 1)], {"unique": True}),
        (db.workspaces, [("join_code", 1)], {"unique": True, "sparse": True}),
        (db.user_sessions, [("session_token", 1)], {"unique": True}),
        (db.user_sessions, [("expires_at", 1)], {"expireAfterSeconds": 0}),
        (db.paddle_events, [("_id", 1)], {"unique": True}),
        (db.paddle_intents, [("_id", 1)], {"unique": True}),
        (db.paddle_intents, [("created_at", 1)], {"expireAfterSeconds": 3600}),
        (db.deals, [("workspace_id", 1)], {}),
        (db.financial_entries, [("workspace_id", 1)], {}),
        (db.activities, [("workspace_id", 1)], {}),
        (db.updates, [("workspace_id", 1)], {}),
        (db.chat_messages, [("workspace_id", 1)], {}),
    ]
    for collection, keys, opts in specs:
        try:
            await asyncio.wait_for(collection.create_index(keys, **opts), timeout=1.5)
        except Exception:
            logger.debug("index ensure skipped for %s", keys, exc_info=True)


@app.on_event("startup")
async def startup():
    # Do not block Render health checks — indexes run in background after listen.
    asyncio.create_task(_ensure_indexes())
    asyncio.create_task(clerk_auth.ensure_allowed_origins())


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
