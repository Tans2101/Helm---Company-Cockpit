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

from seed_data import build_workspace

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

# ------------------------- Roles / permissions -------------------------
MEMBER_PERMS = {"read", "tasks:move", "ask:use"}
OWNER_PERMS = MEMBER_PERMS | {
    "decisions:act", "briefing:generate", "reports:pack", "integrations:manage",
    "billing:manage", "members:manage", "workspace:edit",
}


def perms_for(role: str):
    return OWNER_PERMS if role == "owner" else MEMBER_PERMS


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
    doc = build_workspace(ws_id, f"{first}'s Company", user["user_id"])
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
    return {
        "user_id": user["user_id"], "email": user["email"], "name": user.get("name"),
        "picture": user.get("picture"), "workspace_id": membership["workspace_id"],
        "role": membership["role"],
    }


def require(action: str):
    async def dep(principal=Depends(get_principal)):
        if action not in perms_for(principal["role"]):
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return principal
    return dep


async def get_ws(workspace_id: str):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


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
    doc = build_workspace(ws_id, payload.name.strip() or "New Company", principal["user_id"])
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
    mems = await db.memberships.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).to_list(100)
    out = []
    for m in mems:
        u = await db.users.find_one({"user_id": m.get("user_id")}, {"_id": 0, "name": 1, "picture": 1}) if m.get("user_id") else None
        out.append({
            "membership_id": m["membership_id"], "email": m["email"], "role": m["role"],
            "status": m["status"], "name": (u or {}).get("name"), "picture": (u or {}).get("picture"),
            "is_self": m.get("user_id") == principal["user_id"],
        })
    return {"members": out, "my_role": principal["role"]}


class InviteInput(BaseModel):
    email: EmailStr
    role: str = "member"


@api_router.post("/members/invite")
async def invite_member(payload: InviteInput, request: Request, principal=Depends(require("members:manage"))):
    role = "owner" if payload.role == "owner" else "member"
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
    return {"ok": True, "auto_joined": bool(existing_user), "email_sent": email_result.get("sent", False)}


class RoleInput(BaseModel):
    role: str


@api_router.patch("/members/{membership_id}")
async def update_member_role(membership_id: str, payload: RoleInput, principal=Depends(require("members:manage"))):
    m = await db.memberships.find_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.get("user_id") == principal["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    role = "owner" if payload.role == "owner" else "member"
    await db.memberships.update_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"$set": {"role": role}})
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
            "role": principal["role"], "workspace_id": c["workspace_id"]}


@api_router.get("/briefing")
async def briefing(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    b = c["briefing"]
    is_pro = c["plan"] == "pro"
    return {**b, "is_pro": is_pro, "ai_summary": b.get("ai_summary") if is_pro else None}


@api_router.post("/briefing/generate")
async def generate_briefing(principal=Depends(require("briefing:generate"))):
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    b = c["briefing"]
    context = {"company": c["name"], "metrics": b["metrics"], "what_changed": b["what_changed"],
               "decisions": b["what_to_decide"], "financials": {k: c["financials"][k] for k in ["mrr", "arr", "runway_months", "burn", "cash"]}}
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"briefing-{c['workspace_id']}",
                   system_message=("You are Helm, an executive chief-of-staff AI for a startup CEO. Write a crisp morning briefing in 3-4 sentences. Synthesis over raw data, signal over noise. Lead with what matters most, name the single most important decision, and end with a confident recommendation. No fluff, no lists.")
                   ).with_model("anthropic", "claude-sonnet-4-6")
    text = await chat.send_message(UserMessage(text=f"Company data for today:\n{json.dumps(context, indent=2)}\n\nWrite the CEO's morning briefing."))
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"briefing.ai_summary": text}})
    return {"ai_summary": text}


@api_router.get("/decisions")
async def decisions(principal=Depends(get_principal)):
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
async def telemetry(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return c["telemetry"]


@api_router.get("/financials")
async def financials(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return c["financials"]


@api_router.get("/tasks")
async def tasks(principal=Depends(get_principal)):
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
async def reports(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return {"reports": c["reports"], "is_pro": c["plan"] == "pro"}


@api_router.post("/reports/weekly-pack")
async def weekly_pack(principal=Depends(require("reports:pack"))):
    c = await get_ws(principal["workspace_id"])
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    context = {"company": c["name"], "financials": {k: c["financials"][k] for k in ["mrr", "arr", "runway_months", "burn"]},
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
    return c["people"]


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
               "financials": {k: c["financials"][k] for k in ["mrr", "arr", "runway_months", "burn", "cash", "gross_margin"]},
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
