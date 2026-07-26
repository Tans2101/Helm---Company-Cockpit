import os
import uuid
import json
import hmac
import hashlib
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

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

app = FastAPI()
api_router = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kalun")

# ------------------------- Roles / permissions (access packs) -------------------------
# Packs are presets: owner runs the company; exec sees everything; department
# operators (finance/hr/sales/ops) write their lane; member is general read + light work.
ACCESS_PACKS = ("owner", "exec", "finance", "hr", "sales", "ops", "member")

COMMON = {"read", "tasks:move", "ask:use"}
PACK_PERMS = {
    "owner": COMMON | {
        "decisions:act", "briefing:generate", "reports:pack", "integrations:manage",
        "billing:manage", "members:manage", "workspace:edit",
        "finance:write", "people:write", "sales:write", "ops:write",
    },
    "exec": COMMON | {"decisions:act", "briefing:generate", "reports:pack"},
    "finance": COMMON | {"finance:write"},
    "hr": COMMON | {"people:write"},
    "sales": COMMON | {"sales:write"},
    "ops": COMMON | {"ops:write"},
    "member": set(COMMON),
}

# Empty set = all modules. Restricted packs only see their workbench + shared tools.
PACK_MODULES = {
    "owner": set(),
    "exec": set(),
    "member": set(),
    "finance": {"briefing", "financials", "tasks", "ask"},
    "hr": {"briefing", "people", "team", "tasks", "ask"},
    "sales": {"briefing", "telemetry", "tasks", "ask"},
    "ops": {"briefing", "telemetry", "tasks", "team", "ask"},
}

PACK_HOME = {
    "owner": "/app",
    "exec": "/app",
    "member": "/app",
    "finance": "/app/financials",
    "hr": "/app/people",
    "sales": "/app/telemetry",
    "ops": "/app/tasks",
}


def normalize_role(role: Optional[str]) -> str:
    r = (role or "member").strip().lower()
    return r if r in ACCESS_PACKS else "member"


def perms_for(role: str):
    return set(PACK_PERMS.get(normalize_role(role), PACK_PERMS["member"]))


def modules_for(role: str):
    return set(PACK_MODULES.get(normalize_role(role), set()))


def can_access_module(role: str, module: str) -> bool:
    mods = modules_for(role)
    return (not mods) or (module in mods)


def home_for(role: str) -> str:
    return PACK_HOME.get(normalize_role(role), "/app")


# ------------------------- OAuth state signing (CSRF) -------------------------
_STATE_SECRET = (EMERGENT_LLM_KEY or "kalun-oauth-state").encode()


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
    """Ensure the user belongs to at least one workspace; create one seeded if not."""
    await _activate_invites(user)
    m = await db.memberships.find_one({"user_id": user["user_id"], "status": "active"}, {"_id": 0})
    if m:
        return
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    first = (user.get("name") or "My").split(" ")[0]
    doc = build_workspace(ws_id, f"{first}'s Company", user["user_id"], empty=True)
    await db.workspaces.insert_one(doc)
    await db.memberships.insert_one({
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}",
        "workspace_id": ws_id, "user_id": user["user_id"], "email": user["email"],
        "role": "owner", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": ws_id}})


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
    role = normalize_role(membership.get("role"))
    return {
        "user_id": user["user_id"], "email": user["email"], "name": user.get("name"),
        "picture": user.get("picture"), "workspace_id": membership["workspace_id"],
        "role": role,
        "perms": sorted(perms_for(role)),
        "modules": sorted(modules_for(role)),
        "home": home_for(role),
    }


def require(action: str):
    async def dep(principal=Depends(get_principal)):
        if action not in perms_for(principal["role"]):
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return principal
    return dep


def require_module(module: str):
    async def dep(principal=Depends(get_principal)):
        if not can_access_module(principal["role"], module):
            raise HTTPException(status_code=403, detail=f"Your role cannot access {module}")
        return principal
    return dep


async def record_activity(workspace_id: str, principal: dict, module: str, action: str,
                          summary: str, tone: str = "neutral", detail: Optional[str] = None):
    """Append an activity event and surface it on the CEO Briefing what_changed feed."""
    now = datetime.now(timezone.utc).isoformat()
    actor = principal.get("name") or principal.get("email") or "Teammate"
    event = {
        "id": f"act_{uuid.uuid4().hex[:10]}",
        "workspace_id": workspace_id,
        "actor_user_id": principal["user_id"],
        "actor_name": actor,
        "module": module,
        "action": action,
        "summary": summary,
        "detail": detail or f"{actor} · {module}",
        "tone": tone,
        "created_at": now,
    }
    await db.activity_events.insert_one(event)
    item = {"title": summary, "detail": event["detail"], "tone": tone, "source": "activity", "at": now}
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "briefing.what_changed": 1})
    changed = list(((ws or {}).get("briefing") or {}).get("what_changed") or [])
    changed = [item] + [c for c in changed if not (c.get("source") == "activity" and c.get("title") == summary)]
    await db.workspaces.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"briefing.what_changed": changed[:12]}},
    )
    return event


async def get_ws(workspace_id: str):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


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
async def auth_me(principal=Depends(get_principal)):
    return principal


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
async def create_workspace(payload: CreateWsInput, principal=Depends(get_principal)):
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    doc = build_workspace(ws_id, payload.name.strip() or "New Company", principal["user_id"], empty=True)
    await db.workspaces.insert_one(doc)
    await db.memberships.insert_one({
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
        "user_id": principal["user_id"], "email": principal["email"], "role": "owner",
        "status": "active", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one({"user_id": principal["user_id"]}, {"$set": {"active_workspace_id": ws_id}})
    return {"ok": True, "workspace_id": ws_id}


@api_router.get("/members")
async def list_members(principal=Depends(get_principal)):
    if not can_access_module(principal["role"], "members"):
        raise HTTPException(status_code=403, detail="Your role cannot access members")
    mems = await db.memberships.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).to_list(100)
    out = []
    for m in mems:
        u = await db.users.find_one({"user_id": m.get("user_id")}, {"_id": 0, "name": 1, "picture": 1}) if m.get("user_id") else None
        out.append({
            "membership_id": m["membership_id"], "email": m["email"], "role": normalize_role(m.get("role")),
            "status": m["status"], "name": (u or {}).get("name"), "picture": (u or {}).get("picture"),
            "is_self": m.get("user_id") == principal["user_id"],
        })
    return {"members": out, "my_role": principal["role"], "packs": list(ACCESS_PACKS)}


class InviteInput(BaseModel):
    email: EmailStr
    role: str = "member"


@api_router.post("/members/invite")
async def invite_member(payload: InviteInput, request: Request, principal=Depends(require("members:manage"))):
    role = normalize_role(payload.role)
    email = payload.email.strip().lower()
    existing = await db.memberships.find_one({"workspace_id": principal["workspace_id"], "email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Already a member or invited")
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    await db.memberships.insert_one({
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": principal["workspace_id"],
        "user_id": existing_user["user_id"] if existing_user else None, "email": email,
        "role": role, "status": "active" if existing_user else "invited",
        "invite_token": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    ws = await get_ws(principal["workspace_id"])
    app_url = str(request.base_url).rstrip("/")
    email_result = await send_invite_email(email, principal.get("name") or "Your team lead", ws["name"], role, app_url)
    return {"ok": True, "auto_joined": bool(existing_user), "email_sent": email_result.get("sent", False), "role": role}


class RoleInput(BaseModel):
    role: str


@api_router.patch("/members/{membership_id}")
async def update_member_role(membership_id: str, payload: RoleInput, principal=Depends(require("members:manage"))):
    m = await db.memberships.find_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.get("user_id") == principal["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    role = normalize_role(payload.role)
    await db.memberships.update_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"$set": {"role": role}})
    return {"ok": True, "role": role}


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
    if payload.template == "sample":
        fresh = build_workspace(ws_id, (await get_ws(ws_id))["name"], principal["user_id"], empty=False)
        fresh.pop("workspace_id", None)
        fresh.pop("plan", None)
        fresh.pop("created_at", None)
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": fresh})
        await db.financial_entries.delete_many({"workspace_id": ws_id})
        await db.financial_entries.insert_many(sample_financial_entries(ws_id))
    else:
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": {"onboarding_done": True}})
    return {"ok": True}


@api_router.get("/briefing")
async def briefing(principal=Depends(require_module("briefing"))):
    c = await get_ws(principal["workspace_id"])
    b = dict(c["briefing"])
    is_pro = c["plan"] == "pro"
    fin = await compute_financials(c["workspace_id"])
    metrics = [
        {"label": "MRR", "value": fin["mrr"], "delta": fin["mrr_delta"], "tone": "positive"},
        {"label": "Runway", "value": f"{fin['runway_months']}mo" if fin["runway_months"] else "—", "delta": 0, "tone": "neutral"},
        {"label": "Burn", "value": fin["burn"], "delta": 0, "tone": fin["burn_tone"]},
        {"label": "Headcount", "value": str(c.get("employees") or 0), "delta": 0, "tone": "neutral"},
    ]
    nrr = b.get("nrr")
    if nrr:
        metrics.append({"label": "NRR", "value": nrr["value"], "delta": nrr["delta"], "tone": nrr["tone"]})
    b["metrics"] = metrics
    return {**b, "is_pro": is_pro, "ai_summary": b.get("ai_summary") if is_pro else None}


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
async def decisions(principal=Depends(require_module("decisions"))):
    c = await get_ws(principal["workspace_id"])
    return {"decisions": c["decisions"], "is_pro": c["plan"] == "pro", "can_act": "decisions:act" in perms_for(principal["role"])}


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
async def telemetry(principal=Depends(require_module("telemetry"))):
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
    perms = perms_for(principal["role"])
    tel["can_write_sales"] = "sales:write" in perms
    tel["can_write_ops"] = "ops:write" in perms
    return tel


class SalesSnapshotInput(BaseModel):
    pipeline: str
    pipeline_delta: Optional[float] = None
    customers: Optional[str] = None
    customers_delta: Optional[float] = None
    funnel: Optional[list] = None


@api_router.put("/telemetry/sales")
async def update_sales_snapshot(payload: SalesSnapshotInput, principal=Depends(require("sales:write"))):
    c = await get_ws(principal["workspace_id"])
    tel = dict(c.get("telemetry") or {})
    kpis = [dict(k) for k in tel.get("kpis") or []]

    def upsert_kpi(label, value, delta):
        for k in kpis:
            if k.get("label") == label:
                k["value"] = value
                if delta is not None:
                    k["delta"] = delta
                    k["tone"] = "positive" if delta >= 0 else "negative"
                return
        kpis.append({"label": label, "value": value, "unit": "", "delta": delta or 0,
                     "tone": "positive" if (delta or 0) >= 0 else "negative", "spark": []})

    upsert_kpi("Pipeline", payload.pipeline.strip(), payload.pipeline_delta)
    if payload.customers is not None and str(payload.customers).strip():
        upsert_kpi("Active Customers", str(payload.customers).strip(), payload.customers_delta)
    tel["kpis"] = kpis
    if payload.funnel is not None:
        clean = []
        for row in payload.funnel:
            if not isinstance(row, dict):
                continue
            stage = str(row.get("stage") or "").strip()
            if not stage:
                continue
            try:
                value = int(row.get("value") or 0)
            except (TypeError, ValueError):
                value = 0
            clean.append({"stage": stage, "value": value})
        tel["funnel"] = clean
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"telemetry": tel}})
    await record_activity(
        principal["workspace_id"], principal, "telemetry", "sales",
        f"Updated sales pipeline to {payload.pipeline.strip()}",
        tone="positive", detail=f"{principal.get('name') or 'Sales'} refreshed pipeline / funnel",
    )
    return {"ok": True}


class RiskInput(BaseModel):
    name: str
    likelihood: int
    impact: int
    category: str = "Ops"


@api_router.post("/telemetry/risks")
async def add_risk(payload: RiskInput, principal=Depends(require("ops:write"))):
    if not (1 <= payload.likelihood <= 5 and 1 <= payload.impact <= 5):
        raise HTTPException(status_code=400, detail="likelihood and impact must be 1–5")
    c = await get_ws(principal["workspace_id"])
    tel = dict(c.get("telemetry") or {})
    risks = list(tel.get("risks") or [])
    risk = {"id": f"r_{uuid.uuid4().hex[:8]}", "name": payload.name.strip(),
            "likelihood": payload.likelihood, "impact": payload.impact,
            "category": payload.category.strip() or "Ops"}
    risks.append(risk)
    tel["risks"] = risks
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"telemetry": tel}})
    await record_activity(
        principal["workspace_id"], principal, "telemetry", "risk_create",
        f"Flagged risk · {risk['name']}",
        tone="negative", detail=f"{principal.get('name') or 'Ops'} added a {risk['category']} risk",
    )
    return {"ok": True, "risk": risk}


@api_router.patch("/telemetry/risks/{risk_id}")
async def edit_risk(risk_id: str, payload: RiskInput, principal=Depends(require("ops:write"))):
    if not (1 <= payload.likelihood <= 5 and 1 <= payload.impact <= 5):
        raise HTTPException(status_code=400, detail="likelihood and impact must be 1–5")
    c = await get_ws(principal["workspace_id"])
    tel = dict(c.get("telemetry") or {})
    risks = list(tel.get("risks") or [])
    found = False
    for r in risks:
        if r.get("id") == risk_id:
            r["name"] = payload.name.strip()
            r["likelihood"] = payload.likelihood
            r["impact"] = payload.impact
            r["category"] = payload.category.strip() or "Ops"
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Risk not found")
    tel["risks"] = risks
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"telemetry": tel}})
    await record_activity(
        principal["workspace_id"], principal, "telemetry", "risk_update",
        f"Updated risk · {payload.name.strip()}",
        tone="neutral", detail=f"{principal.get('name') or 'Ops'} updated risk scoring",
    )
    return {"ok": True}


@api_router.delete("/telemetry/risks/{risk_id}")
async def delete_risk(risk_id: str, principal=Depends(require("ops:write"))):
    c = await get_ws(principal["workspace_id"])
    tel = dict(c.get("telemetry") or {})
    risks = list(tel.get("risks") or [])
    kept = [r for r in risks if r.get("id") != risk_id]
    if len(kept) == len(risks):
        raise HTTPException(status_code=404, detail="Risk not found")
    name = next((r.get("name") for r in risks if r.get("id") == risk_id), "risk")
    tel["risks"] = kept
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"telemetry": tel}})
    await record_activity(
        principal["workspace_id"], principal, "telemetry", "risk_delete",
        f"Cleared risk · {name}",
        tone="positive", detail=f"{principal.get('name') or 'Ops'} removed a risk",
    )
    return {"ok": True}


@api_router.get("/financials")
async def financials(principal=Depends(require_module("financials"))):
    fin = await compute_financials(principal["workspace_id"])
    entries = await db.financial_entries.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("month", -1).to_list(5000)
    return {**fin, "entries": entries, "can_write": "finance:write" in perms_for(principal["role"]),
            "can_manage": "integrations:manage" in perms_for(principal["role"])}


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
    tone = "positive" if payload.type == "revenue" else "negative"
    await record_activity(
        principal["workspace_id"], principal, "financials", "create",
        f"Logged {payload.type} · {fmt_money(payload.amount)} ({payload.category.strip() or 'Other'})",
        tone=tone, detail=f"{principal.get('name') or 'Finance'} added a {payload.month} {payload.type} entry",
    )
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
    await record_activity(
        principal["workspace_id"], principal, "financials", "update",
        f"Updated {payload.type} · {fmt_money(payload.amount)} ({payload.category.strip() or 'Other'})",
        tone="neutral", detail=f"{principal.get('name') or 'Finance'} edited a ledger entry",
    )
    return {"ok": True}


@api_router.delete("/financials/entries/{entry_id}")
async def delete_fin_entry(entry_id: str, principal=Depends(require("finance:write"))):
    existing = await db.financial_entries.find_one({"id": entry_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    await db.financial_entries.delete_one({"id": entry_id, "workspace_id": principal["workspace_id"]})
    label = (existing or {}).get("category") or "entry"
    await record_activity(
        principal["workspace_id"], principal, "financials", "delete",
        f"Removed finance entry · {label}",
        tone="negative", detail=f"{principal.get('name') or 'Finance'} deleted a ledger entry",
    )
    return {"ok": True}


class FinSettingsInput(BaseModel):
    cash: float
    gross_margin: Optional[float] = None


@api_router.put("/financials/settings")
async def update_fin_settings(payload: FinSettingsInput, principal=Depends(require("finance:write"))):
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]},
                                   {"$set": {"financial_settings.cash": round(payload.cash, 2),
                                             "financial_settings.gross_margin": payload.gross_margin}})
    await record_activity(
        principal["workspace_id"], principal, "financials", "settings",
        f"Updated cash position to {fmt_money(payload.cash)}",
        tone="neutral", detail=f"{principal.get('name') or 'Finance'} updated financial settings",
    )
    return {"ok": True}


@api_router.post("/financials/import/stripe")
async def import_stripe_revenue(principal=Depends(require("finance:write"))):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=400, detail="Stripe not configured")
    stripe_sdk.api_key = STRIPE_API_KEY
    from collections import defaultdict
    by_month = defaultdict(float)
    try:
        charges = await asyncio.to_thread(lambda: stripe_sdk.Charge.list(limit=100))
        for ch in charges.get("data", []):
            if ch.get("paid") and ch.get("status") == "succeeded" and not ch.get("refunded"):
                dt = datetime.fromtimestamp(ch["created"], tz=timezone.utc)
                by_month[dt.strftime("%Y-%m")] += (ch.get("amount", 0) / 100.0)
    except Exception as e:
        logger.exception("stripe import failed")
        raise HTTPException(status_code=400, detail=f"Stripe import failed: {e}")
    now = datetime.now(timezone.utc).isoformat()
    docs = [{"id": f"fe_{uuid.uuid4().hex[:10]}", "workspace_id": principal["workspace_id"], "type": "revenue",
             "category": "Stripe revenue", "amount": round(amt, 2), "month": month, "recurring": True,
             "note": "Imported from Stripe", "source": "stripe", "created_by": principal["user_id"], "created_at": now}
            for month, amt in by_month.items()]
    if docs:
        await db.financial_entries.delete_many({"workspace_id": principal["workspace_id"], "source": "stripe"})
        await db.financial_entries.insert_many(docs)
        await record_activity(
            principal["workspace_id"], principal, "financials", "import",
            f"Imported Stripe revenue · {len(docs)} month(s)",
            tone="positive", detail=f"{principal.get('name') or 'Finance'} synced Stripe charges",
        )
    return {"ok": True, "months_imported": len(docs), "total": round(sum(by_month.values()), 2)}


@api_router.get("/tasks")
async def tasks(principal=Depends(require_module("tasks"))):
    c = await get_ws(principal["workspace_id"])
    return c["tasks"]


class TaskMove(BaseModel):
    column: str


@api_router.patch("/tasks/{task_id}")
async def move_task(task_id: str, payload: TaskMove, principal=Depends(require("tasks:move"))):
    c = await get_ws(principal["workspace_id"])
    t = c["tasks"]
    for item in t["items"]:
        if item["id"] == task_id:
            item["column"] = payload.column
            break
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"tasks": t}})
    return {"ok": True}


@api_router.get("/reports")
async def reports(principal=Depends(require_module("reports"))):
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
async def team(principal=Depends(require_module("team"))):
    c = await get_ws(principal["workspace_id"])
    return c["team"]


@api_router.get("/calendar")
async def calendar(principal=Depends(require_module("calendar"))):
    c = await get_ws(principal["workspace_id"])
    data = dict(c["calendar"])
    data["live"] = bool(c.get("google_tokens"))
    return data


@api_router.get("/people")
async def people(principal=Depends(require_module("people"))):
    c = await get_ws(principal["workspace_id"])
    block = c.get("people") or {"people": [], "avg_trust": 0}
    roster = list(block.get("people") or [])
    avg = round(sum(int(p.get("trust_score") or 0) for p in roster) / len(roster)) if roster else 0
    return {
        "people": roster,
        "avg_trust": avg,
        "headcount": len(roster),
        "can_write": "people:write" in perms_for(principal["role"]),
    }


class PersonInput(BaseModel):
    name: str
    role: str
    department: str
    trust_score: int = 80
    quality: str = "B+"
    tasks_done: int = 0
    tenure: str = "0y"


def _normalize_person(payload: PersonInput, existing_id: Optional[str] = None):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    trust = max(0, min(100, int(payload.trust_score)))
    return {
        "id": existing_id or f"p_{uuid.uuid4().hex[:8]}",
        "name": name,
        "role": payload.role.strip() or "Teammate",
        "department": payload.department.strip() or "General",
        "trust_score": trust,
        "quality": payload.quality.strip() or "B+",
        "tasks_done": max(0, int(payload.tasks_done or 0)),
        "tenure": payload.tenure.strip() or "0y",
    }


async def _persist_roster(workspace_id: str, roster: list):
    avg = round(sum(int(p.get("trust_score") or 0) for p in roster) / len(roster)) if roster else 0
    ws = await get_ws(workspace_id)
    team = dict(ws.get("team") or {"members": [], "avg_utilization": 0, "overloaded_count": 0})
    by_name = {m.get("name"): m for m in (team.get("members") or []) if m.get("name")}
    synced = []
    for p in roster:
        existing = by_name.get(p["name"])
        if existing:
            synced.append({**existing, "role": p.get("role") or existing.get("role")})
        else:
            synced.append({
                "name": p["name"], "role": p.get("role") or "Teammate",
                "utilization": 70, "status": "healthy", "capacity": 40, "allocated": 28,
            })
    overloaded = sum(1 for m in synced if (m.get("utilization") or 0) >= 100)
    avg_util = round(sum(m.get("utilization") or 0 for m in synced) / len(synced)) if synced else 0
    team = {"members": synced, "avg_utilization": avg_util, "overloaded_count": overloaded}
    await db.workspaces.update_one(
        {"workspace_id": workspace_id},
        {"$set": {
            "people": {"people": roster, "avg_trust": avg},
            "employees": len(roster),
            "team": team,
        }},
    )
    return avg


@api_router.post("/people")
async def add_person(payload: PersonInput, principal=Depends(require("people:write"))):
    c = await get_ws(principal["workspace_id"])
    roster = list((c.get("people") or {}).get("people") or [])
    person = _normalize_person(payload)
    roster.append(person)
    await _persist_roster(principal["workspace_id"], roster)
    await record_activity(
        principal["workspace_id"], principal, "people", "create",
        f"Added {person['name']} · {person['role']} ({person['department']})",
        tone="positive", detail=f"{principal.get('name') or 'HR'} updated the roster · headcount {len(roster)}",
    )
    return {"ok": True, "person": person, "headcount": len(roster)}


@api_router.patch("/people/{person_id}")
async def edit_person(person_id: str, payload: PersonInput, principal=Depends(require("people:write"))):
    c = await get_ws(principal["workspace_id"])
    roster = list((c.get("people") or {}).get("people") or [])
    idx = next((i for i, p in enumerate(roster) if p.get("id") == person_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Person not found")
    person = _normalize_person(payload, existing_id=person_id)
    roster[idx] = person
    await _persist_roster(principal["workspace_id"], roster)
    await record_activity(
        principal["workspace_id"], principal, "people", "update",
        f"Updated {person['name']} · {person['department']}",
        tone="neutral", detail=f"{principal.get('name') or 'HR'} edited roster details",
    )
    return {"ok": True, "person": person}


@api_router.delete("/people/{person_id}")
async def delete_person(person_id: str, principal=Depends(require("people:write"))):
    c = await get_ws(principal["workspace_id"])
    roster = list((c.get("people") or {}).get("people") or [])
    target = next((p for p in roster if p.get("id") == person_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Person not found")
    roster = [p for p in roster if p.get("id") != person_id]
    await _persist_roster(principal["workspace_id"], roster)
    await record_activity(
        principal["workspace_id"], principal, "people", "delete",
        f"Removed {target.get('name')} from roster",
        tone="negative", detail=f"{principal.get('name') or 'HR'} · headcount now {len(roster)}",
    )
    return {"ok": True, "headcount": len(roster)}


# ------------------------- Ask Helm -------------------------
class AskInput(BaseModel):
    message: str


@api_router.get("/ask/history")
async def ask_history(principal=Depends(require_module("ask"))):
    msgs = await db.chat_messages.find({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


@api_router.post("/ask")
async def ask_kalun(payload: AskInput, principal=Depends(require("ask:use"))):
    if not can_access_module(principal["role"], "ask"):
        raise HTTPException(status_code=403, detail="Your role cannot access ask")
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
    if not can_access_module(principal["role"], "integrations"):
        raise HTTPException(status_code=403, detail="Your role cannot access integrations")
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
    return {"integrations": ints, "is_pro": c["plan"] == "pro", "can_manage": "integrations:manage" in perms_for(principal["role"])}


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
class CheckoutInput(BaseModel):
    origin_url: str


def get_stripe(request: Request) -> StripeCheckout:
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{str(request.base_url)}api/webhook/stripe")


@api_router.get("/billing/plans")
async def billing_plans(principal=Depends(get_principal)):
    if not can_access_module(principal["role"], "billing"):
        raise HTTPException(status_code=403, detail="Your role cannot access billing")
    c = await get_ws(principal["workspace_id"])
    return {"current_plan": c["plan"], "pro_price": PRO_PRICE, "can_manage": "billing:manage" in perms_for(principal["role"])}


@api_router.post("/payments/checkout")
async def create_checkout(payload: CheckoutInput, request: Request, principal=Depends(require("billing:manage"))):
    stripe_checkout = get_stripe(request)
    success_url = f"{payload.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{payload.origin_url}/payment/cancel"
    req = CheckoutSessionRequest(amount=PRO_PRICE, currency="usd", success_url=success_url, cancel_url=cancel_url,
                                 metadata={"workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "plan": "pro"})
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({"session_id": session.session_id, "workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "amount": PRO_PRICE, "currency": "usd", "plan": "pro", "status": "initiated", "payment_status": "pending", "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"checkout_url": session.url, "session_id": session.session_id}


@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result.session_id and result.payment_status == "paid":
        rec = await db.payment_transactions.find_one({"session_id": result.session_id}, {"_id": 0})
        await db.payment_transactions.update_one({"session_id": result.session_id, "payment_status": {"$ne": "paid"}}, {"$set": {"status": "completed", "payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}})
        if rec and rec.get("workspace_id"):
            await db.workspaces.update_one({"workspace_id": rec["workspace_id"]}, {"$set": {"plan": "pro"}})
    return {"status": "ok"}


@api_router.post("/demo/reset-plan")
async def reset_plan(principal=Depends(require("billing:manage"))):
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": {"plan": "free"}})
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"service": "Helm CEO Operating System"}


app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origin_regex=".*", allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.memberships.create_index([("user_id", 1), ("workspace_id", 1)])
    await db.memberships.create_index([("email", 1), ("status", 1)])
    await db.workspaces.create_index("workspace_id", unique=True)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
