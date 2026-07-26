import os
import re
import uuid
import json
import hmac
import html
import secrets
import hashlib
import asyncio
import logging
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
import resend
import stripe as stripe_sdk
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse, RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest, CheckoutStatusResponse,
)

from seed_data import build_workspace, sample_financial_entries

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
QB_CLIENT_ID = os.environ.get('QUICKBOOKS_CLIENT_ID', '')
QB_CLIENT_SECRET = os.environ.get('QUICKBOOKS_CLIENT_SECRET', '')
QB_ENV = os.environ.get('QUICKBOOKS_ENV', 'sandbox')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
PRO_PRICE = 149.0
# Prefer a dedicated secret; fall back to LLM key. Dev-only literal is last resort so
# process restarts do not invalidate in-flight OAuth state.
_STATE_SECRET = (os.environ.get("OAUTH_STATE_SECRET") or EMERGENT_LLM_KEY or "helm-oauth-state-dev-only").encode()
# Comma-separated frontend origins for CORS + checkout redirect allowlist.
_CORS_ORIGINS = [o.strip().rstrip("/") for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if o.strip()]
# Keep Emergent preview frontends working without opening CORS to the entire internet.
_CORS_ORIGIN_REGEX = os.environ.get(
    "CORS_ORIGIN_REGEX",
    r"https://([a-z0-9-]+\.)*(emergentagent\.com|emergent\.sh)",
)
DEMO_RESET_ENABLED = os.environ.get("DEMO_RESET_ENABLED", "true").lower() in ("1", "true", "yes")

app = FastAPI()
api_router = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helm")

# In-memory join attempt tracker: user_id -> [timestamps]. Process-local is enough for preview.
_JOIN_ATTEMPTS: dict[str, list[float]] = {}
_JOIN_LIMIT = 8
_JOIN_WINDOW_SEC = 600

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
             "sales": "/app/me", "ops": "/app/me"}
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
def _sign_state(provider: str, workspace_id: str, user_id: str = "") -> str:
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    body = f"{provider}:{workspace_id}:{ts}:{user_id}"
    sig = hmac.new(_STATE_SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}:{sig}"


def _verify_state(state: str, max_age: int = 600):
    try:
        parts = state.split(":")
        if len(parts) == 5:
            provider, workspace_id, ts, user_id, sig = parts
            body = f"{provider}:{workspace_id}:{ts}:{user_id}"
        elif len(parts) == 4:
            # Legacy states (pre user_id binding / truncated sig)
            provider, workspace_id, ts, sig = parts
            user_id = ""
            body = f"{provider}:{workspace_id}:{ts}"
        else:
            return None
    except (ValueError, AttributeError):
        return None
    expected = hmac.new(_STATE_SECRET, body.encode(), hashlib.sha256).hexdigest()
    # Accept both full and legacy truncated signatures during rollout.
    if not (hmac.compare_digest(expected, sig) or hmac.compare_digest(expected[:16], sig)):
        return None
    try:
        age = int(datetime.now(timezone.utc).timestamp()) - int(ts)
    except ValueError:
        return None
    if age > max_age:
        return None
    return provider, workspace_id, user_id


def _new_join_code() -> str:
    """12-char hex join code (~48 bits). Longer than the old 6-char codes."""
    return secrets.token_hex(6).upper()


def _rate_limit_join(user_id: str):
    now = time.time()
    recent = [t for t in _JOIN_ATTEMPTS.get(user_id, []) if now - t < _JOIN_WINDOW_SEC]
    if len(recent) >= _JOIN_LIMIT:
        raise HTTPException(status_code=429, detail="Too many join attempts. Try again later.")
    recent.append(now)
    _JOIN_ATTEMPTS[user_id] = recent


def _origin_allowed(origin_url: str) -> bool:
    """Allow checkout redirects only to configured frontends / Emergent previews."""
    try:
        parsed = urlparse(origin_url.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if parsed.username or parsed.password:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if origin in _CORS_ORIGINS:
        return True
    try:
        return bool(re.fullmatch(_CORS_ORIGIN_REGEX, origin))
    except re.error:
        return False


# ------------------------- Email (Resend) -------------------------
def _invite_email_html(inviter_name: str, workspace_name: str, role: str, app_url: str) -> str:
    inviter_name = html.escape(inviter_name or "")
    workspace_name = html.escape(workspace_name or "")
    role = html.escape(role or "")
    app_url = html.escape(app_url or "", quote=True)
    return f"""\
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#09090b;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#09090b;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#121214;border:1px solid rgba(255,255,255,0.08);border-radius:14px;overflow:hidden;">
<tr><td style="padding:32px 36px 8px 36px;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="width:34px;height:34px;background:rgba(201,169,98,0.15);border:1px solid rgba(201,169,98,0.35);border-radius:8px;text-align:center;vertical-align:middle;color:#c9a962;font-weight:600;font-size:15px;">K</td>
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
    await db.memberships.update_many(
        {"email": user["email"], "status": "invited"},
        {"$set": {"user_id": user["user_id"], "status": "active",
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


@api_router.post("/auth/session")
async def process_session(payload: SessionInput, response: Response):
    async with httpx.AsyncClient() as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": payload.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session id")
    data = r.json()
    email = data["email"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": data.get("name"), "picture": data.get("picture")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": data.get("name"), "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    await _bootstrap(user)
    session_token = data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": expires_at.isoformat(), "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7 * 24 * 60 * 60)
    return {"ok": True, "user_id": user_id, "email": email}


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
                "pack": None, "perms": [], "default_route": "/app/welcome", "pack_label": None,
                "onboarding_done": None}
    pack = pack_of(membership)
    ws = await db.workspaces.find_one({"workspace_id": membership["workspace_id"]},
                                      {"_id": 0, "onboarding_done": 1})
    return {**base, "workspace_id": membership["workspace_id"], "needs_workspace": False,
            "role": membership["role"], "pack": pack, "perms": sorted(perms_for(pack)),
            "default_route": PACK_HOME.get(pack, "/app"), "pack_label": PACK_LABEL.get(pack, "Member"),
            "onboarding_done": (ws or {}).get("onboarding_done", True)}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
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
    _rate_limit_join(user["user_id"])
    code = (code or "").strip().upper()
    if not re.fullmatch(r"[A-F0-9]{6,16}", code):
        raise HTTPException(status_code=404, detail="Invalid invite code")
    ws = await db.workspaces.find_one({"join_code": code}, {"_id": 0, "name": 1, "workspace_id": 1})
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return {"name": ws["name"], "workspace_id": ws["workspace_id"]}


@api_router.post("/workspaces/join")
async def join_workspace(payload: JoinInput, user=Depends(get_user)):
    _rate_limit_join(user["user_id"])
    code = (payload.code or "").strip().upper()
    if not re.fullmatch(r"[A-F0-9]{6,16}", code):
        raise HTTPException(status_code=404, detail="Invalid invite code")
    ws = await db.workspaces.find_one({"join_code": code}, {"_id": 0})
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
    elif existing.get("status") != "active":
        await db.memberships.update_one(
            {"membership_id": existing["membership_id"]},
            {"$set": {"status": "active", "joined_at": datetime.now(timezone.utc).isoformat()}},
        )
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": ws_id}})
    return {"ok": True, "workspace_id": ws_id}


@api_router.get("/workspaces/join-code")
async def get_join_code(principal=Depends(require("members:invite"))):
    ws = await get_ws(principal["workspace_id"])
    code = ws.get("join_code")
    if not code:
        code = _new_join_code()
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
    app_url = str(request.base_url).rstrip("/")
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


@api_router.post("/workspace/apply-template")
async def apply_template(payload: TemplateInput, principal=Depends(require("workspace:edit"))):
    ws_id = principal["workspace_id"]
    if payload.template not in ("sample", "clean"):
        raise HTTPException(status_code=400, detail="Unknown template")
    if payload.template == "sample":
        existing = await get_ws(ws_id)
        fresh = build_workspace(ws_id, existing["name"], principal["user_id"], empty=False)
        # Never wipe identity, billing, invite surface, or OAuth tokens on template apply.
        for key in (
            "workspace_id", "plan", "created_at", "join_code", "name", "owner_user_id",
            "google_tokens", "quickbooks_tokens", "stripe_secret_key",
        ):
            fresh.pop(key, None)
        fresh["onboarding_done"] = True
        fresh["template"] = "sample"
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": fresh})
        await db.financial_entries.delete_many({"workspace_id": ws_id})
        await db.financial_entries.insert_many(sample_financial_entries(ws_id))
    else:
        await db.workspaces.update_one(
            {"workspace_id": ws_id},
            {"$set": {"onboarding_done": True, "template": "empty"}},
        )
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
    b = c["briefing"]
    context = {"company": c["name"], "metrics": b.get("what_to_decide"), "what_changed": b["what_changed"],
               "decisions": b["what_to_decide"], "financials": await compute_financials(c["workspace_id"])}
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"briefing-{c['workspace_id']}",
                   system_message=("You are Helm, an executive chief-of-staff AI for a startup CEO. Write a crisp morning briefing in 3-4 sentences. Synthesis over raw data, signal over noise. Lead with what matters most, name the single most important decision, and end with a confident recommendation. No fluff, no lists.")
                   ).with_model("anthropic", "claude-sonnet-4-6")
    text = await chat.send_message(UserMessage(text=f"Company data for today:\n{json.dumps(context, indent=2)}\n\nWrite the CEO's morning briefing."))
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


@api_router.get("/telemetry")
async def telemetry(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    tel = dict(c["telemetry"])
    fin = await compute_financials(c["workspace_id"])
    kpis = [dict(k) for k in tel.get("kpis", [])]
    for k in kpis:
        if k["label"] == "MRR":
            k["value"] = fin["mrr"]
            k["delta"] = fin["mrr_delta"]
            if fin["spark"]:
                k["spark"] = fin["spark"]
    tel["kpis"] = kpis
    if fin["revenue_series"]:
        tel["revenue_trend"] = [{"month": r["month"], "mrr": r["revenue"], "target": round(r["revenue"] * 1.03)} for r in fin["revenue_series"]]
    return tel


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


def _validate_fin_entry(payload: FinEntryInput):
    if payload.type not in ("revenue", "expense"):
        raise HTTPException(status_code=400, detail="type must be revenue or expense")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", payload.month or ""):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    if payload.amount < 0 or payload.amount > 1e12:
        raise HTTPException(status_code=400, detail="amount out of range")


@api_router.post("/financials/entries")
async def add_fin_entry(payload: FinEntryInput, principal=Depends(require("finance:write"))):
    _validate_fin_entry(payload)
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
    _validate_fin_entry(payload)
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


@api_router.post("/financials/import/stripe")
async def import_stripe_revenue(principal=Depends(require("finance:write"))):
    """Import Stripe charges using the workspace's own key — never the platform billing key."""
    ws = await get_ws(principal["workspace_id"])
    workspace_key = (ws.get("stripe_secret_key") or "").strip()
    if not workspace_key:
        raise HTTPException(
            status_code=400,
            detail="Connect a workspace Stripe secret key before importing revenue. "
                   "Platform billing credentials cannot be used for tenant imports.",
        )
    stripe_sdk.api_key = workspace_key
    from collections import defaultdict
    by_month = defaultdict(float)
    try:
        charges = await asyncio.to_thread(lambda: stripe_sdk.Charge.list(limit=100))
        for ch in charges.get("data", []):
            if ch.get("paid") and ch.get("status") == "succeeded" and not ch.get("refunded"):
                dt = datetime.fromtimestamp(ch["created"], tz=timezone.utc)
                by_month[dt.strftime("%Y-%m")] += (ch.get("amount", 0) / 100.0)
    except Exception:
        logger.exception("stripe import failed")
        raise HTTPException(status_code=400, detail="Stripe import failed. Check the workspace Stripe key.")
    now = datetime.now(timezone.utc).isoformat()
    docs = [{"id": f"fe_{uuid.uuid4().hex[:10]}", "workspace_id": principal["workspace_id"], "type": "revenue",
             "category": "Stripe revenue", "amount": round(amt, 2), "month": month, "recurring": True,
             "note": "Imported from Stripe", "source": "stripe", "created_by": principal["user_id"], "created_at": now}
            for month, amt in by_month.items()]
    if docs:
        await db.financial_entries.delete_many({"workspace_id": principal["workspace_id"], "source": "stripe"})
        await db.financial_entries.insert_many(docs)
        await log_activity(principal, "financials", "import.stripe",
                           f"Imported {len(docs)} month(s) of Stripe revenue ({fmt_money(sum(by_month.values()))})")
    return {"ok": True, "months_imported": len(docs), "total": round(sum(by_month.values()), 2)}


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
    return {"reports": c["reports"], "is_pro": c["plan"] == "pro"}


@api_router.post("/reports/weekly-pack")
async def weekly_pack(principal=Depends(require("reports:pack"))):
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    context = {"company": c["name"], "financials": await compute_financials(c["workspace_id"]),
               "kpis": c["telemetry"]["kpis"], "reports": [{"title": r["title"], "summary": r["summary"]} for r in c["reports"]]}
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"pack-{c['workspace_id']}",
                   system_message=("You are Helm, writing the Weekly CEO Pack. Produce a board-ready weekly summary in markdown with sections: Headline, Growth, Financial Health, Risks, and This Week's Focus. Be concise, executive, and specific.")
                   ).with_model("anthropic", "claude-sonnet-4-6")
    text = await chat.send_message(UserMessage(text=f"Data:\n{json.dumps(context, indent=2)}\n\nWrite the Weekly CEO Pack."))
    return {"content": text}


@api_router.get("/team")
async def team(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return c["team"]


@api_router.get("/calendar")
async def calendar(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    data = dict(c["calendar"])
    data["live"] = bool(c.get("google_tokens"))
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
async def ask_kalun(payload: AskInput, principal=Depends(require("ask:use"))):
    c = await get_ws(principal["workspace_id"])
    is_pro = c["plan"] == "pro"
    if not is_pro:
        today = datetime.now(timezone.utc).date().isoformat()
        count = await db.chat_messages.count_documents({"workspace_id": c["workspace_id"], "user_id": principal["user_id"], "role": "user", "day": today})
        if count >= 5:
            raise HTTPException(status_code=402, detail="Free plan limited to 5 messages/day. Upgrade to Pro for unlimited.")
    now = datetime.now(timezone.utc)
    await db.chat_messages.insert_one({"workspace_id": c["workspace_id"], "user_id": principal["user_id"], "role": "user", "content": payload.message, "created_at": now.isoformat(), "day": now.date().isoformat()})
    context = {"company": c["name"], "stage": c["stage"], "employees": c["employees"],
               "financials": await compute_financials(c["workspace_id"]),
               "kpis": c["telemetry"]["kpis"], "open_decisions": [d["title"] for d in c["decisions"] if d["status"] == "pending"], "risks": c["telemetry"]["risks"]}
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"ask-{c['workspace_id']}-{principal['user_id']}",
                   system_message=(f"You are Helm, the CEO's executive AI chief-of-staff for {c['name']} (a {c['stage']} startup, {c['employees']} people). Answer like a sharp, trusted operator: direct, quantified, decisive. Use the live company data provided. Synthesis over raw data, signal over noise. Keep answers tight. Current company snapshot:\n{json.dumps(context, indent=2)}")
                   ).with_model("anthropic", "claude-sonnet-4-6")

    async def gen():
        collected = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=payload.message)):
                if isinstance(ev, TextDelta):
                    collected += ev.content
                    yield ev.content
                elif isinstance(ev, StreamDone):
                    break
        except Exception:
            logger.exception("chat stream error")
            if not collected:
                collected = "I hit an error reaching my reasoning engine. Please try again."
                yield collected
        finally:
            await db.chat_messages.insert_one({"workspace_id": c["workspace_id"], "user_id": principal["user_id"], "role": "assistant", "content": collected, "created_at": datetime.now(timezone.utc).isoformat(), "day": datetime.now(timezone.utc).date().isoformat()})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
              "scope": cfg["scope"],
              "state": _sign_state(provider, principal["workspace_id"], principal["user_id"]),
              **cfg.get("extra", {})}
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
    # If state was bound to a user, require that same user to complete the callback.
    bound_user = verified[2] if len(verified) > 2 else ""
    if bound_user:
        try:
            actor = await _user_from_request(request)
        except HTTPException:
            return RedirectResponse(f"{frontend}/integrations?error=state")
        if actor["user_id"] != bound_user:
            return RedirectResponse(f"{frontend}/integrations?error=state")
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
class CheckoutInput(BaseModel):
    origin_url: str


def get_stripe(request: Request) -> StripeCheckout:
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{str(request.base_url)}api/webhook/stripe")


@api_router.get("/billing/plans")
async def billing_plans(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return {"current_plan": c["plan"], "pro_price": PRO_PRICE, "can_manage": "billing:manage" in perms_for(principal["pack"])}


@api_router.post("/payments/checkout")
async def create_checkout(payload: CheckoutInput, request: Request, principal=Depends(require("billing:manage"))):
    origin = (payload.origin_url or "").strip().rstrip("/")
    if not _origin_allowed(origin):
        raise HTTPException(status_code=400, detail="origin_url is not an allowed frontend origin")
    stripe_checkout = get_stripe(request)
    success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/payment/cancel"
    req = CheckoutSessionRequest(amount=PRO_PRICE, currency="usd", success_url=success_url, cancel_url=cancel_url,
                                 metadata={"workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "plan": "pro"})
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({"session_id": session.session_id, "workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "amount": PRO_PRICE, "currency": "usd", "plan": "pro", "status": "initiated", "payment_status": "pending", "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"checkout_url": session.url, "session_id": session.session_id}


@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request, user=Depends(get_user)):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    allowed = record.get("user_id") == user["user_id"]
    if not allowed and record.get("workspace_id"):
        mem = await db.memberships.find_one({
            "workspace_id": record["workspace_id"], "user_id": user["user_id"], "status": "active",
        }, {"_id": 0})
        allowed = bool(mem)
    if not allowed:
        # Same status as missing — avoid leaking other workspaces' session ids.
        raise HTTPException(status_code=404, detail="Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            status: CheckoutStatusResponse = await get_stripe(request).get_checkout_status(session_id)
            if status.payment_status == "paid" or status.status == "complete":
                await db.payment_transactions.update_one({"session_id": session_id, "payment_status": {"$ne": "paid"}}, {"$set": {"status": "completed", "payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}})
                if record.get("workspace_id"):
                    await db.workspaces.update_one({"workspace_id": record["workspace_id"]}, {"$set": {"plan": "pro"}})
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except Exception:
            logger.exception("stripe status check failed")
    return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    try:
        result = await get_stripe(request).handle_webhook(body, request.headers.get("Stripe-Signature"))
    except Exception:
        logger.exception("stripe webhook failed")
        raise HTTPException(status_code=400, detail="Invalid webhook")
    if result.session_id and result.payment_status == "paid":
        rec = await db.payment_transactions.find_one({"session_id": result.session_id}, {"_id": 0})
        await db.payment_transactions.update_one({"session_id": result.session_id, "payment_status": {"$ne": "paid"}}, {"$set": {"status": "completed", "payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}})
        if rec and rec.get("workspace_id"):
            await db.workspaces.update_one({"workspace_id": rec["workspace_id"]}, {"$set": {"plan": "pro"}})
    return {"status": "ok"}


@api_router.post("/demo/reset-plan")
async def reset_plan(principal=Depends(require("billing:manage"))):
    if not DEMO_RESET_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": {"plan": "free"}})
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"service": "Helm CEO Operating System"}


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept"],
)


@app.on_event("startup")
async def startup():
    await db.memberships.create_index([("user_id", 1), ("workspace_id", 1)])
    await db.memberships.create_index([("email", 1), ("status", 1)])
    await db.workspaces.create_index("workspace_id", unique=True)
    await db.workspaces.create_index("join_code")
    await db.user_sessions.create_index("session_token", unique=True)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
