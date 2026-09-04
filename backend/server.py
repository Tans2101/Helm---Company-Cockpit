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
from datetime import date, datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse
from collections import defaultdict

import httpx
import jwt
import resend
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse, RedirectResponse, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr

import llm as helm_llm
import document_cleanup
import rate_limit as doc_rate_limit
import storage as doc_storage
import quickbooks as qb_sync
import google_oauth as gcal
import integrations_catalog as integ_catalog
import clerk_auth
import decision_engine
import money_fmt
from money_fmt import fmt_money, normalize_currency, currency_symbol, CURRENCY_SYMBOLS
from pagination import clamp_limit, apply_before_filter, next_cursor
from helm_config import HELM_CANONICAL_ORIGIN, is_stale_deploy_url, public_api_origin, registrable_cookie_domain
from static_frontend import mount_static_frontend, should_serve_static
from seed_data import build_workspace, sample_financial_entries, gen_join_code
import access_sections as sec_access
import plans as helm_plans
import plan_usage
import departments_catalog as dept_catalog
import department_access as dept_access
import department_migrate as dept_migrate

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helm")


def _mongo_candidate_urls() -> list[str]:
    """Ordered Mongo URLs to try — Render pserv first unless USE_ATLAS_MONGO=true."""
    seen: set[str] = set()
    urls: list[str] = []

    def add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    use_atlas = os.environ.get("USE_ATLAS_MONGO", "").lower() in ("1", "true", "yes")
    hostport = os.environ.get("MONGO_HOSTPORT", "").strip()
    host = os.environ.get("MONGO_HOST", "").strip()
    atlas = os.environ.get("MONGO_URL", "").strip()

    def add_pserv() -> None:
        if hostport:
            add(f"mongodb://{hostport}")
            return
        if not host and os.environ.get("RENDER"):
            host_local = "helm-mongo"
        else:
            host_local = host
        if host_local:
            add(f"mongodb://{host_local}:27017")

    if use_atlas:
        if atlas:
            add(atlas)
        # Atlas-only mode: skip Render pserv probe (avoids false "2 candidates failed" on startup).
        return urls

    # Default (Render blueprint): private Mongo first; stale Atlas URL is fallback only.
    add_pserv()
    if atlas:
        add(atlas)
    return urls


def _redact_mongo_url(url: str) -> str:
    if "@" not in url:
        return url
    prefix, rest = url.split("@", 1)
    return f"{prefix.split('://')[0]}://***@{rest}"


def _mongo_source_label(url: str) -> str:
    if url.startswith("mongodb+srv://"):
        return "atlas"
    if "helm-mongo" in url or os.environ.get("MONGO_HOST", "").strip() in url:
        return "render_pserv"
    if os.environ.get("MONGO_HOST", "").strip():
        return "mongo_host"
    return "mongo_url"


def _resolve_mongo_url() -> tuple[str, str]:
    """Pick Mongo URL without blocking import — health check probes connectivity."""
    candidates = _mongo_candidate_urls()
    if not candidates:
        raise RuntimeError("Set MONGO_URL (Atlas) or sync render.yaml for MONGO_HOST / helm-mongo")
    url = candidates[0]
    return url, _mongo_source_label(url)


DB_NAME = os.environ["DB_NAME"]


# -----------------------------------------------------------------------------
# Environment configuration
#
# ENVIRONMENT=production enforces the go-live checklist below. Keep in sync with
# DEPLOY.md § "Deploy API on Render" and README.md § "Go-live checklist".
#
# Required before ENVIRONMENT=production:
#   MONGO_URL          Atlas URI (or MONGO_HOST / helm-mongo on Render blueprint)
#   DB_NAME            Database name (e.g. helm)
#   SESSION_SECRET     Long random string — never use placeholders in production
#   OAUTH_STATE_SECRET Long random string — required in production (no fallback)
#   FRONTEND_URL       Public app URL (e.g. https://www.helmcontrol.online)
#   APP_URL            Same as FRONTEND_URL for post-OAuth redirects
#   CORS_ORIGINS       Comma-separated allowed browser origins (same as frontend)
#   COOKIE_SECURE      true behind HTTPS
#   COOKIE_SAMESITE    lax when Vercel rewrites /api → Render (same-origin cookies);
#                      none + COOKIE_SECURE=true when the browser calls Render directly
#   ALLOW_DEMO_LOGIN   false
#   DEMO_RESET_ENABLED false (recommended)
#   CLERK_SECRET_KEY + CLERK_JWKS_URL   OR   GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET
#   ANTHROPIC_API_KEY  AI briefing / Ask Helm
#   PADDLE_*           Billing (when BILLING_ENFORCED=true)
#
# Development: leave ENVIRONMENT unset or set to "development" — placeholders are OK.
# -----------------------------------------------------------------------------

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()

def _make_mongo_client(url: str) -> AsyncIOMotorClient:
    is_atlas = url.startswith("mongodb+srv://")
    return AsyncIOMotorClient(
        url,
        serverSelectionTimeoutMS=8000 if is_atlas else 3000,
        connectTimeoutMS=8000 if is_atlas else 3000,
        socketTimeoutMS=10000,
    )


mongo_url, MONGO_SOURCE = _resolve_mongo_url()
client = _make_mongo_client(mongo_url)
db = client[DB_NAME]

SESSION_SECRET = os.environ.get('SESSION_SECRET', 'change-me-in-production')
FRONTEND_URL = os.environ.get('FRONTEND_URL', '').strip().rstrip('/')
if is_stale_deploy_url(FRONTEND_URL):
    FRONTEND_URL = HELM_CANONICAL_ORIGIN
ALLOW_DEMO_LOGIN = os.environ.get("ALLOW_DEMO_LOGIN", "false").lower() in ("1", "true", "yes")
DEMO_RESET_ENABLED = os.environ.get("DEMO_RESET_ENABLED", "false").lower() in ("1", "true", "yes")
# HTTPS cookies: default false for local dev; set true on Render (see DEPLOY.md).
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
# Default lax — correct when Vercel rewrites /api to Render (browser sees same-origin).
# If REACT_APP_BACKEND_URL points at Render directly, set COOKIE_SAMESITE=none and COOKIE_SECURE=true.
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET", "")
if not OAUTH_STATE_SECRET:
    OAUTH_STATE_SECRET = SESSION_SECRET
APP_URL = (os.environ.get("APP_URL") or FRONTEND_URL or "").rstrip("/")
if is_stale_deploy_url(APP_URL):
    APP_URL = HELM_CANONICAL_ORIGIN
# Display fallback — tier prices live in plans.PLANS; PRO_PRICE kept for legacy envs.
PRO_PRICE = float(os.environ.get("PRO_PRICE", "99"))
# When false (default), feature gates are open; paywall + quotas apply when true.
BILLING_ENFORCED = os.environ.get("BILLING_ENFORCED", "false").lower() in ("1", "true", "yes")
TRIAL_DAYS = helm_plans.TRIAL_DAYS
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
PADDLE_WEBHOOK_SECRET = os.environ.get('PADDLE_WEBHOOK_SECRET', '')
PADDLE_ENV = os.environ.get('PADDLE_ENV', 'sandbox')
PADDLE_API_BASE = "https://sandbox-api.paddle.com" if PADDLE_ENV == "sandbox" else "https://api.paddle.com"
CLERK_PUBLISHABLE_KEY = clerk_auth.resolve_clerk_publishable_key()
SETUP_SECRET = os.environ.get("SETUP_SECRET", "").strip()

_INSECURE_SESSION_SECRETS = frozenset({
    "change-me-in-production",
    "change-me-to-a-long-random-string",
})


def _enforce_production_config() -> None:
    """Refuse to boot with known-insecure settings when ENVIRONMENT=production."""
    if ENVIRONMENT != "production":
        return
    problems: list[str] = []
    raw_session = (os.environ.get("SESSION_SECRET") or "").strip()
    if not raw_session or SESSION_SECRET in _INSECURE_SESSION_SECRETS:
        problems.append("SESSION_SECRET must be set to a strong random value (not a placeholder)")
    if not (os.environ.get("OAUTH_STATE_SECRET") or "").strip():
        problems.append("OAUTH_STATE_SECRET must be set explicitly in production")
    if not CORS_ORIGINS:
        problems.append("CORS_ORIGINS must list your frontend origin(s)")
    if ALLOW_DEMO_LOGIN:
        problems.append("ALLOW_DEMO_LOGIN must be false in production")
    if problems:
        raise RuntimeError(
            "Production configuration invalid (ENVIRONMENT=production):\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\nSee DEPLOY.md and the config header in server.py."
        )


_enforce_production_config()

app = FastAPI()
api_router = APIRouter(prefix="/api")

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
    "ops": BASE_PERMS | {"ops:write", "telemetry:write"},
    "exec": BASE_PERMS | {
        "decisions:act", "briefing:generate", "reports:pack", "reports:write",
        "telemetry:write",
        "members:invite", "tasks:assign",
    },
    "owner": BASE_PERMS | {
        "finance:write", "people:write", "sales:write", "ops:write",
        "decisions:act", "briefing:generate", "reports:pack", "reports:write",
        "telemetry:write",
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


async def _membership_for(principal: dict) -> dict:
    return await db.memberships.find_one(
        {"user_id": principal["user_id"], "workspace_id": principal["workspace_id"], "status": "active"},
        {"_id": 0},
    ) or {}


async def workspace_departments(workspace_id: str, ws: dict | None = None) -> list[str]:
    """Departments actually in use — members, roster, and existing access rules."""
    if ws is None:
        ws = await get_ws(workspace_id)
    depts: set[str] = set()
    mems = await db.memberships.find(
        {"workspace_id": workspace_id, "status": {"$in": ["active", "invited"]}},
        {"_id": 0, "department": 1},
    ).to_list(200)
    for m in mems:
        d = (m.get("department") or "General").strip()
        if d:
            depts.add(d)
    for p in (ws.get("people") or {}).get("people") or []:
        d = (p.get("department") or "").strip()
        if d:
            depts.add(d)
    for section_depts in (ws.get("section_access") or {}).values():
        if isinstance(section_depts, list):
            for d in section_depts:
                if str(d).strip():
                    depts.add(str(d).strip())
    if not depts:
        depts.add("General")
    return sorted(depts, key=lambda x: (x != "General", x.lower()))


def _avg_trust(people_list):
    scores = [p.get("trust_score", 0) for p in people_list if isinstance(p.get("trust_score"), (int, float))]
    return round(sum(scores) / len(scores)) if scores else 0


def _display_name_from_email(email: str) -> str:
    local = (email or "").split("@")[0]
    cleaned = re.sub(r"[._+\-]+", " ", local).strip()
    return cleaned.title() if cleaned else "Team member"


def _find_linked_person(roster: list, membership: dict):
    mid = membership.get("membership_id")
    email = _normalize_email(membership.get("email") or "")
    user_id = membership.get("user_id")
    for p in roster:
        if mid and p.get("membership_id") == mid:
            return p
    for p in roster:
        if email and _normalize_email(p.get("email") or "") == email:
            return p
    if user_id:
        for p in roster:
            if p.get("user_id") == user_id:
                return p
    return None


async def ensure_person_for_membership(workspace_id: str, membership: dict, name: str | None = None) -> dict:
    """Upsert a People roster row for a Team & Access membership. Members always appear in People."""
    ws = await get_ws(workspace_id)
    people = dict(ws.get("people") or {"people": [], "avg_trust": 0})
    roster = list(people.get("people") or [])
    people["people"] = roster

    email = _normalize_email(membership.get("email") or "")
    user_id = membership.get("user_id")
    dept = (membership.get("department") or "General").strip() or "General"
    display_name = (name or "").strip() or None
    if not display_name and user_id:
        u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1})
        display_name = ((u or {}).get("name") or "").strip() or None
    if not display_name:
        display_name = _display_name_from_email(email)

    found = _find_linked_person(roster, membership)
    if found:
        found["membership_id"] = membership["membership_id"]
        if email:
            found["email"] = email
        if user_id:
            found["user_id"] = user_id
        if dept:
            found["department"] = dept
        # Prefer a real account name over an email-derived placeholder
        if name and name.strip():
            found["name"] = name.strip()
        elif user_id and display_name and (
            not found.get("name")
            or (email and found.get("name") == _display_name_from_email(email))
        ):
            found["name"] = display_name
        person = found
    else:
        person = {
            "id": f"p_{uuid.uuid4().hex[:8]}",
            "name": display_name,
            "role": "",
            "department": dept,
            "trust_score": 80,
            "quality": "B+",
            "tasks_done": 0,
            "tenure": "New",
            "membership_id": membership["membership_id"],
            "email": email or None,
            "user_id": user_id,
        }
        roster.append(person)

    people["avg_trust"] = _avg_trust(roster)
    headcount = len(roster)
    await db.workspaces.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"people": people, "employees": headcount}},
    )
    return person


async def sync_members_into_people(workspace_id: str) -> dict:
    """Backfill: every active/invited membership has a People row."""
    mems = await db.memberships.find(
        {"workspace_id": workspace_id, "status": {"$in": ["active", "invited"]}},
        {"_id": 0},
    ).to_list(200)
    for m in mems:
        await ensure_person_for_membership(workspace_id, m)
    return await get_ws(workspace_id)


async def unlink_person_membership(workspace_id: str, membership_id: str):
    """Keep the roster person when access is revoked — just clear the login link."""
    ws = await get_ws(workspace_id)
    people = dict(ws.get("people") or {"people": [], "avg_trust": 0})
    changed = False
    for p in people.get("people") or []:
        if p.get("membership_id") == membership_id:
            p.pop("membership_id", None)
            changed = True
    if changed:
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"people": people}},
        )


async def can_section_write(principal: dict, section_id: str, pack_perm: str) -> bool:
    """Pack permission OR CEO-granted member/department access for a section."""
    if pack_perm in perms_for(principal["pack"]):
        return True
    membership = await _membership_for(principal)
    # Per-member grants (preferred)
    if section_id in sec_access.normalize_section_grants(membership.get("section_grants")):
        return True
    # Legacy department grants
    ws = await get_ws(principal["workspace_id"])
    dept = (membership.get("department") or "General").strip()
    allowed = (ws.get("section_access") or {}).get(section_id) or []
    return dept in allowed


def require_section(section_id: str, pack_perm: str):
    """Section write access — Free may edit manually; AI upload uses a separate feature gate."""
    async def dep(principal=Depends(get_principal)):
        if not await can_section_write(principal, section_id, pack_perm):
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return principal
    return dep


def _normalize_task_columns(tasks: dict) -> dict:
    """Display label Backlog → To-Do while keeping column id backlog."""
    out = dict(tasks)
    cols = []
    for col in out.get("columns") or []:
        c = dict(col)
        if c.get("id") == "backlog":
            c["name"] = "To-Do"
        cols.append(c)
    out["columns"] = cols
    return out


# ------------------------- OAuth state signing (CSRF) -------------------------
_STATE_SECRET = OAUTH_STATE_SECRET.encode()


def _allowed_auth_redirect(url: str) -> bool:
    """Only allow post-login redirects to our frontend origins (open-redirect guard)."""
    if not url:
        return False
    if url.startswith("/") and not url.startswith("//"):
        return True
    bases = {APP_URL.rstrip("/")} if APP_URL else set()
    bases.update(o.rstrip("/") for o in CORS_ORIGINS if o)
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


async def send_resend_email(*, to: list, subject: str, html: str) -> dict:
    """Shared Resend send helper (best-effort). `to` may include multiple recipients in one send."""
    recipients = [e for e in (to or []) if e and "@" in str(e)]
    if not recipients:
        return {"sent": False, "reason": "no_recipients"}
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping email: %s", subject)
        return {"sent": False, "reason": "no_key"}
    resend.api_key = RESEND_API_KEY
    params = {"from": SENDER_EMAIL, "to": recipients, "subject": subject, "html": html}
    try:
        email = await asyncio.to_thread(resend.Emails.send, params)
        logger.info("resend sent subject=%r to=%s id=%s", subject, recipients, (email or {}).get("id"))
        return {"sent": True, "id": (email or {}).get("id"), "to": recipients}
    except Exception:
        logger.exception("resend send failed subject=%r to=%s", subject, recipients)
        return {"sent": False, "reason": "error"}


async def send_notification_email(to: str | list, subject: str, body: str) -> dict:
    """Reusable single/multi-recipient notification email via Resend. Never raises."""
    recipients = to if isinstance(to, list) else [to]
    return await send_resend_email(to=recipients, subject=subject, html=body)


def _app_base_url() -> str:
    return (APP_URL or FRONTEND_URL or HELM_CANONICAL_ORIGIN or "").rstrip("/")


def _task_delegation_email_html(
    *,
    task_title: str,
    task_note: str,
    delegator_name: str,
    workspace_name: str,
    task_url: str,
) -> str:
    title = html.escape(task_title or "Task")
    note = html.escape((task_note or "").strip()[:400])
    delegator = html.escape(delegator_name or "A teammate")
    workspace = html.escape(workspace_name or "your company")
    url = html.escape(task_url, quote=True)
    note_block = (
        f'<p style="color:#a1a1aa;font-size:14px;line-height:1.6;margin:14px 0 0 0;">{note}</p>'
        if note else ""
    )
    return f"""\
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#09090b;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#09090b;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#121214;border:1px solid rgba(255,255,255,0.08);border-radius:14px;overflow:hidden;">
<tr><td style="padding:32px 36px 8px 36px;">
<p style="color:#c9a962;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0;">Task delegated</p>
<h1 style="color:#ffffff;font-size:22px;font-weight:400;margin:10px 0 0 0;line-height:1.3;">{title}</h1>
<p style="color:#a1a1aa;font-size:15px;line-height:1.6;margin:16px 0 0 0;">{delegator} assigned you a task in <b style="color:#ffffff;">{workspace}</b> on Helm.</p>
{note_block}
<table cellpadding="0" cellspacing="0" style="margin:28px 0 8px 0;"><tr>
<td style="background:#c9a962;border-radius:8px;">
<a href="{url}" style="display:inline-block;padding:12px 26px;color:#09090b;font-size:14px;font-weight:600;text-decoration:none;">Open task in Helm &rarr;</a>
</td></tr></table>
</td></tr>
</table>
</td></tr></table></body></html>"""


async def notify_task_delegated(
    *,
    assignee_user_id: str | None,
    previous_assignee_user_id: str | None,
    task: dict,
    principal: dict,
    workspace_name: str,
) -> dict:
    """Send delegation email only when assignee changes to a different user. Never raises / never blocks."""
    new_uid = (assignee_user_id or "").strip() or None
    old_uid = (previous_assignee_user_id or "").strip() or None
    if not new_uid or new_uid == old_uid:
        return {"sent": False, "reason": "unchanged"}
    if new_uid == principal.get("user_id"):
        return {"sent": False, "reason": "self_assign"}
    try:
        user = await db.users.find_one({"user_id": new_uid}, {"_id": 0, "email": 1, "name": 1})
        email = _normalize_email((user or {}).get("email") or "")
        if not email:
            mem = await db.memberships.find_one(
                {"workspace_id": principal["workspace_id"], "user_id": new_uid},
                {"_id": 0, "email": 1},
            )
            email = _normalize_email((mem or {}).get("email") or "")
        if not email:
            logger.info("task delegation email skipped — no email for user_id=%s", new_uid)
            return {"sent": False, "reason": "no_email"}
        title = (task.get("title") or "Task").strip()
        note = (task.get("note") or task.get("tag") or "").strip()
        task_url = f"{_app_base_url()}/app/tasks?task={task.get('id') or ''}"
        html_body = _task_delegation_email_html(
            task_title=title,
            task_note=note,
            delegator_name=principal.get("name") or principal.get("email") or "A teammate",
            workspace_name=workspace_name,
            task_url=task_url,
        )
        result = await send_notification_email(
            email,
            f"Delegated to you: {title}",
            html_body,
        )
        return result
    except Exception:
        logger.exception("notify_task_delegated failed for task=%s", task.get("id"))
        return {"sent": False, "reason": "error"}


async def post_slack_webhook(webhook_url: str, text: str) -> dict:
    """Best-effort Slack Incoming Webhook post. Never raises."""
    url = (webhook_url or "").strip()
    if not url.startswith("https://hooks.slack.com/"):
        return {"ok": False, "reason": "invalid_or_missing"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json={"text": text})
        if r.status_code >= 400:
            logger.warning("slack webhook failed status=%s body=%s", r.status_code, r.text[:200])
            return {"ok": False, "reason": "http_error", "status": r.status_code}
        return {"ok": True}
    except Exception:
        logger.exception("slack webhook post failed")
        return {"ok": False, "reason": "error"}


# Packs that should receive high-severity CEO alerts (owner + executive/"manager")
ALERT_RECIPIENT_PACKS = frozenset({"owner", "exec"})


async def _alert_recipient_emails(workspace_id: str) -> list[str]:
    mems = await db.memberships.find(
        {"workspace_id": workspace_id, "status": "active"},
        {"_id": 0, "user_id": 1, "pack": 1, "role": 1, "email": 1},
    ).to_list(200)
    emails = []
    seen = set()
    for m in mems:
        if pack_of(m) not in ALERT_RECIPIENT_PACKS and m.get("role") != "owner":
            continue
        email = (m.get("email") or "").strip().lower()
        if not email:
            u = await db.users.find_one({"user_id": m["user_id"]}, {"_id": 0, "email": 1})
            email = ((u or {}).get("email") or "").strip().lower()
        if email and email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


async def _notify_high_severity_alerts(workspace_id: str, decision_suggestions: list, c: dict) -> dict:
    """Email + optional Slack for newly seen high-severity signals. Best-effort; never blocks."""
    import alert_notify as an

    notified = set(c.get("notified_signal_ids") or [])
    fresh = an.new_high_alerts(decision_suggestions, notified)
    if not fresh:
        return {"emailed": False, "slack": False, "new_alerts": 0}

    app_url = APP_URL or FRONTEND_URL or HELM_CANONICAL_ORIGIN
    ws_name = c.get("name") or "Your workspace"
    html = an.build_alert_email_html(ws_name, fresh, app_url)
    slack_text = an.build_slack_text(ws_name, fresh, app_url)
    recipients = await _alert_recipient_emails(workspace_id)
    email_result = await send_resend_email(
        to=recipients,
        subject=f"Helm alert: {len(fresh)} high-severity signal{'s' if len(fresh) != 1 else ''} — {ws_name}",
        html=html,
    )
    slack_result = {"ok": False, "reason": "not_configured"}
    webhook = (c.get("slack_webhook_url") or "").strip()
    if webhook:
        slack_result = await post_slack_webhook(webhook, slack_text)

    new_keys = [an.signal_notify_key(s.get("signal") or s) for s in fresh]
    delivered = bool(email_result.get("sent")) or bool(slack_result.get("ok"))
    # Only debounce after at least one channel succeeds — failed delivery must retry
    if delivered:
        updated_ids = list(notified | set(new_keys))
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {
                "notified_signal_ids": updated_ids,
                "notified_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    return {
        "emailed": bool(email_result.get("sent")),
        "slack": bool(slack_result.get("ok")),
        "new_alerts": len(fresh),
        "debounced": delivered,
        "email": email_result,
        "slack_result": slack_result,
    }


# ------------------------- Auth / principal -------------------------
def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


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
    # Enroll into Sales / Accounting & Finance when those departments exist.
    mems = await db.memberships.find(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0, "workspace_id": 1},
    ).to_list(50)
    for m in mems:
        ws_id = m.get("workspace_id")
        if ws_id:
            await dept_migrate.enroll_user_in_sales_finance(db, ws_id, user["user_id"])


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


def workspace_plan_id(ws_or_plan) -> str:
    plan = ws_or_plan.get("plan") if isinstance(ws_or_plan, dict) else ws_or_plan
    return helm_plans.normalize_plan(plan)


def workspace_is_pro(ws_or_plan) -> bool:
    """True when billing is off, or workspace is on a paid tier (Starter+). Legacy name kept for API fields."""
    if not BILLING_ENFORCED:
        return True
    return helm_plans.is_paid_plan(workspace_plan_id(ws_or_plan))


def workspace_allows(ws_or_plan, feature: str) -> bool:
    """Plan feature gate. past_due / paused subscriptions lose paid features."""
    if not helm_plans.plan_allows(workspace_plan_id(ws_or_plan), feature, billing_enforced=BILLING_ENFORCED):
        return False
    if not BILLING_ENFORCED:
        return True
    if isinstance(ws_or_plan, dict):
        status = (ws_or_plan.get("subscription_status") or ws_or_plan.get("billing_status") or "").lower()
        if status in ("past_due", "paused", "canceled", "cancelled"):
            return False
    return True


def _valid_fin_month(month: str) -> bool:
    import finance_recurrence as fin_recur
    return fin_recur.is_valid_month((month or "").strip())


async def require_pro(principal=Depends(get_principal)):
    if not BILLING_ENFORCED:
        return principal
    c = await get_ws(principal["workspace_id"])
    if not helm_plans.is_paid_plan(c.get("plan")):
        raise HTTPException(status_code=403, detail="A paid Helm plan is required for this action")
    return principal


def require_feature(feature: str):
    async def dep(principal=Depends(get_principal)):
        c = await get_ws(principal["workspace_id"])
        if not workspace_allows(c, feature):
            raise HTTPException(
                status_code=403,
                detail=f"Upgrade your plan to use this feature ({feature.replace('_', ' ')})",
            )
        return principal
    return dep


def require_pro_perm(action: str):
    """Pack permission + optional plan feature gate (Free keeps core cockpit writes)."""
    async def dep(principal=Depends(get_principal)):
        if action not in perms_for(principal["pack"]):
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        feature = helm_plans.feature_for_action(action)
        if feature and BILLING_ENFORCED:
            c = await get_ws(principal["workspace_id"])
            if not workspace_allows(c, feature):
                raise HTTPException(
                    status_code=403,
                    detail="Upgrade your plan to use this feature",
                )
        return principal
    return dep


async def _seat_count(workspace_id: str) -> int:
    return await db.memberships.count_documents({
        "workspace_id": workspace_id,
        "status": {"$in": ["active", "invited"]},
    })


async def _enforce_seat_available(workspace_id: str, plan: str | None = None) -> None:
    if not BILLING_ENFORCED:
        return
    if plan is None:
        ws = await get_ws(workspace_id)
        plan = ws.get("plan")
    limit = helm_plans.seats_limit(plan)
    if limit is None:
        return
    used = await _seat_count(workspace_id)
    if used >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Upgrade to add more members — your plan allows {limit} seat{'s' if limit != 1 else ''} ({used}/{limit} used).",
        )


async def _enforce_ai_extract_quota(principal) -> None:
    c = await get_ws(principal["workspace_id"])
    if not workspace_allows(c, helm_plans.FEATURE_AI_EXTRACT):
        raise HTTPException(
            status_code=403,
            detail="AI document upload is not available on the Free plan — upgrade to Starter or higher.",
        )
    if not BILLING_ENFORCED:
        return
    limit = helm_plans.ai_extracts_limit(c.get("plan"))
    if limit <= 0:
        raise HTTPException(
            status_code=403,
            detail="AI document upload is not available on your plan — upgrade to continue.",
        )
    period = plan_usage.current_usage_period(c)
    used = await plan_usage.get_period_extract_count(db, principal["workspace_id"], period["key"])
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail="You've hit this month's document limit — upgrade for more.",
        )


async def get_ws(workspace_id: str):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    # Conscious migration: legacy plan=pro → starter (see DEPLOY.md)
    if ws.get("plan") == "pro":
        await db.workspaces.update_one(
            {"workspace_id": workspace_id, "plan": "pro"},
            {"$set": {"plan": "starter", "plan_migrated_from": "pro"}},
        )
        ws["plan"] = "starter"
        ws["plan_migrated_from"] = "pro"
    # Apply scheduled downgrade when the billing period ends
    pending = ws.get("pending_plan")
    effective_at = plan_usage.parse_dt(ws.get("pending_plan_effective_at"))
    if pending and effective_at and datetime.now(timezone.utc) >= effective_at:
        target = helm_plans.normalize_plan(pending)
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {"plan": target},
                "$unset": {"pending_plan": "", "pending_plan_effective_at": ""},
            },
        )
        ws["plan"] = target
        ws.pop("pending_plan", None)
        ws.pop("pending_plan_effective_at", None)
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


async def _enforce_document_rate_limit(principal, action: str, limit: int, message: str) -> None:
    if await doc_rate_limit.is_over_limit(db, principal["workspace_id"], action, limit):
        label = "Upload" if action == "upload" else "Extraction"
        await log_activity(
            principal, "financials", "document.rate_limit",
            f"{label} limit reached for this workspace ({limit}/hour)",
            {"action": action, "limit": limit},
        )
        raise HTTPException(status_code=429, detail=message)


# ------------------------- Financials (computed from entries) -------------------------
async def _workspace_currency(workspace_id: str) -> str:
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "financial_settings": 1})
    settings = (ws or {}).get("financial_settings") or {}
    return normalize_currency(settings.get("currency"))


async def compute_financials(workspace_id: str, department_ids: Optional[list] = None):
    from collections import defaultdict
    import finance_recurrence as fin_recur

    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "financial_settings": 1})
    settings = (ws or {}).get("financial_settings") or {"cash": 0, "gross_margin": None, "currency": "usd"}
    if not settings.get("currency"):
        settings = {**settings, "currency": "usd"}
    else:
        settings = {**settings, "currency": normalize_currency(settings.get("currency"))}
    currency = settings["currency"]
    entry_filt = dept_access.apply_department_filter(
        {"workspace_id": workspace_id}, department_ids,
    )
    entries = await db.financial_entries.find(entry_filt, {"_id": 0}).to_list(5000)
    # Drop clearly invalid months so one bad CSV row cannot 500 the page
    entries = [e for e in entries if fin_recur.is_valid_month(str(e.get("month") or ""))]
    horizon = fin_recur.resolve_expense_horizon(entries)
    rev_by = defaultdict(float, fin_recur.expand_entries_by_month(entries, entry_type="revenue", horizon_end=horizon))
    exp_by = defaultdict(float, fin_recur.expand_entries_by_month(entries, entry_type="expense", horizon_end=horizon))
    # Recurring-only revenue by month (for MRR) — never mix one-time sales into MRR
    rec_entries = [e for e in entries if e.get("type") == "revenue" and e.get("recurring")]
    rec_by = defaultdict(float, fin_recur.expand_entries_by_month(rec_entries, entry_type="revenue", horizon_end=horizon))
    exp_cat = defaultdict(float)
    cat_totals = fin_recur.expand_expense_category_totals(entries, horizon)
    for _month, cats in cat_totals.items():
        for cat, amt in cats.items():
            exp_cat[cat] += amt
    months = sorted(set(list(rev_by) + list(exp_by)))
    last = months[-6:]

    def lbl(m):
        return datetime.strptime(m, "%Y-%m").strftime("%b")

    revenue_series = [{"month": lbl(m), "revenue": round(rev_by[m]), "expenses": round(exp_by[m])} for m in last]
    burn_series = [{"month": lbl(m), "burn": round(exp_by[m] - rev_by[m])} for m in last]
    latest = months[-1] if months else None
    # MRR is recurring revenue only — never fall back to one-time sales
    mrr_val = float(rec_by[latest]) if latest else 0.0
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
    rec_months = sorted(rec_by.keys())
    if len(rec_months) >= 2:
        prev_m, curr_m = rec_months[-2], rec_months[-1]
        prev_r, curr_r = rec_by[prev_m], rec_by[curr_m]
        if prev_r > 0:
            mrr_delta = round((curr_r - prev_r) / prev_r * 100, 1)
    return {
        "mrr": fmt_money(mrr_val, currency), "arr": fmt_money(mrr_val * 12, currency), "runway_months": runway,
        "burn": fmt_money(burn_val, currency), "cash": fmt_money(cash, currency),
        "gross_margin": ((f"{int(gm)}%" if float(gm).is_integer() else f"{gm}%") if gm is not None else "—"),
        "revenue_series": revenue_series, "burn_series": burn_series, "scenarios": scenarios,
        "expense_breakdown": expense_breakdown, "settings": settings,
        "currency": currency, "currency_symbol": currency_symbol(currency),
        "mrr_delta": mrr_delta, "spark": [r["revenue"] for r in revenue_series],
        "burn_tone": "negative" if burn_val > 0 else "positive", "has_data": bool(entries),
        "mrr_value": round(float(mrr_val or 0)),
        "burn_value": round(float(burn_val or 0)),
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


def _auth_redirect_uri(_request: Request) -> str:
    return f"{public_api_origin()}/api/auth/google/callback"


def _oauth_callback_uri(provider: str) -> str:
    return f"{public_api_origin()}/api/oauth/{provider}/callback"


@api_router.api_route("/clerk-proxy", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def clerk_fapi_proxy_root(request: Request):
    return await clerk_auth.proxy_clerk_fapi("v1/client", request)


@api_router.api_route("/clerk-proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def clerk_fapi_proxy(path: str, request: Request):
    """Browser Clerk SDK proxy — avoids broken clerk.* custom-domain TLS during provisioning."""
    return await clerk_auth.proxy_clerk_fapi(path, request)


@api_router.get("/auth/clerk-edge-secret")
async def clerk_edge_secret(request: Request):
    """Return CLERK_SECRET_KEY to Vercel edge middleware (bootstrap token required)."""
    token = request.headers.get("X-Clerk-Bootstrap", "").strip()
    bootstrap = clerk_auth.CLERK_PROXY_BOOTSTRAP
    if not bootstrap or not token or not hmac.compare_digest(token, bootstrap):
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")
    if not clerk_auth.CLERK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Clerk is not configured on Render")
    return {"clerk_secret_key": clerk_auth.CLERK_SECRET_KEY}


@api_router.get("/auth/config")
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


@api_router.post("/auth/clerk")
async def clerk_login(request: Request, response: Response):
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    await _require_mongo()
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
        "department": membership.get("department") or "General",
        "perms": sorted(perms_for(pack)),
        "default_route": PACK_HOME.get(pack, "/app"),
        "pack_label": PACK_LABEL.get(pack, "Member"),
    }


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


@api_router.post("/auth/clerk/exchange")
async def clerk_exchange(request: Request, response: Response):
    """Clerk JWT → Helm session payload (+ optional httpOnly cookie)."""
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    await _require_mongo()
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


@api_router.get("/auth/me")
async def auth_me(user=Depends(get_user)):
    return await _user_session_payload(user)


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    clear_session_cookie(response)
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
    membership = {
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
        "user_id": user["user_id"], "email": user["email"], "role": "owner",
        "pack": "owner", "department": "General", "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.memberships.insert_one(membership)
    await ensure_person_for_membership(ws_id, membership, name=user.get("name"))
    await dept_migrate.migrate_workspace_sales_finance(db, ws_id)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": ws_id}})
    return {"ok": True, "workspace_id": ws_id}


class JoinInput(BaseModel):
    code: str


async def _find_workspace_by_join_code(code: str):
    """Match invite codes case-insensitively so pasted codes always work."""
    c = (code or "").strip()
    if not c:
        return None
    ws = await db.workspaces.find_one({"join_code": c}, {"_id": 0})
    if ws:
        return ws
    rows = await db.workspaces.find(
        {"join_code": {"$regex": f"^{re.escape(c)}$", "$options": "i"}},
        {"_id": 0},
    ).to_list(1)
    return rows[0] if rows else None


@api_router.get("/workspaces/join-info")
async def join_info(code: str, user=Depends(get_user)):
    ws = await _find_workspace_by_join_code(code)
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return {"name": ws["name"], "workspace_id": ws["workspace_id"]}


@api_router.post("/workspaces/join")
async def join_workspace(payload: JoinInput, request: Request, user=Depends(get_user)):
    _check_join_rate_limit(_client_ip(request))
    ws = await _find_workspace_by_join_code(payload.code)
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    ws_id = ws["workspace_id"]
    existing = await db.memberships.find_one({"workspace_id": ws_id, "user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        await _enforce_seat_available(ws_id, ws.get("plan"))
        membership = {
            "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
            "user_id": user["user_id"], "email": user["email"], "role": "member",
            "pack": "member", "department": "General", "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.memberships.insert_one(membership)
        existing = membership
    await ensure_person_for_membership(ws_id, existing, name=user.get("name"))
    await dept_migrate.enroll_user_in_sales_finance(db, ws_id, user["user_id"])
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": ws_id}})
    return {"ok": True, "workspace_id": ws_id}


@api_router.get("/workspaces/join-code")
async def get_join_code(principal=Depends(require_pro_perm("members:invite"))):
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
        pack = pack_of(m)
        out.append({
            "membership_id": m["membership_id"], "email": m["email"], "role": m["role"],
            "pack": pack, "status": m["status"], "name": (u or {}).get("name"),
            "picture": (u or {}).get("picture"), "user_id": m.get("user_id"),
            "department": m.get("department") or "General",
            "section_grants": sec_access.normalize_section_grants(m.get("section_grants")),
            "is_self": m.get("user_id") == principal["user_id"],
        })
    ws = await get_ws(principal["workspace_id"])
    plan = workspace_plan_id(ws)
    seats = helm_plans.seats_limit(plan)
    return {
        "members": out,
        "my_role": principal["role"],
        "my_pack": principal["pack"],
        "plan": plan,
        "seats_used": len(out),
        "seats_limit": seats,
    }


class InviteInput(BaseModel):
    email: EmailStr
    pack: str = "member"
    department: str = "General"
    name: Optional[str] = None


@api_router.post("/members/invite")
async def invite_member(payload: InviteInput, request: Request, principal=Depends(require_pro_perm("members:invite"))):
    if payload.pack not in VALID_PACKS:
        raise HTTPException(status_code=400, detail="Unknown access pack")
    pack = payload.pack
    if pack == "owner" and "members:manage" not in perms_for(principal["pack"]):
        raise HTTPException(status_code=403, detail="Only an owner can grant owner access")
    await _enforce_seat_available(principal["workspace_id"])
    role = "owner" if pack == "owner" else "member"
    email = payload.email.strip().lower()
    existing = await db.memberships.find_one({"workspace_id": principal["workspace_id"], "email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Already a member or invited")
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    membership = {
        "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": principal["workspace_id"],
        "user_id": existing_user["user_id"] if existing_user else None, "email": email,
        "role": role, "pack": pack, "department": payload.department.strip() or "General",
        "status": "active" if existing_user else "invited",
        "invite_token": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.memberships.insert_one(membership)
    display_name = (existing_user or {}).get("name") or payload.name
    await ensure_person_for_membership(principal["workspace_id"], membership, name=display_name)
    if membership.get("user_id"):
        await dept_migrate.enroll_user_in_sales_finance(
            db, principal["workspace_id"], membership["user_id"],
        )
    ws = await get_ws(principal["workspace_id"])
    app_url = APP_URL or FRONTEND_URL or str(request.base_url).rstrip("/")
    email_result = await send_invite_email(email, principal.get("name") or "Your team lead", ws["name"], PACK_LABEL.get(pack, "Member"), app_url)
    return {"ok": True, "auto_joined": bool(existing_user), "email_sent": email_result.get("sent", False)}


class RoleInput(BaseModel):
    pack: str
    department: Optional[str] = None


@api_router.patch("/members/{membership_id}")
async def update_member_role(membership_id: str, payload: RoleInput, principal=Depends(require_pro_perm("members:invite"))):
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
    upd = {"role": role, "pack": pack}
    if payload.department is not None:
        upd["department"] = payload.department.strip() or "General"
    await db.memberships.update_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"$set": upd})
    m2 = {**m, **upd}
    await ensure_person_for_membership(principal["workspace_id"], m2)
    return {"ok": True}


class SectionAccessInput(BaseModel):
    section_access: dict


class MemberGrantsInput(BaseModel):
    """Map membership_id → list of manageable section ids the CEO grants that person."""
    grants: dict


@api_router.get("/access/sections")
async def get_section_access(principal=Depends(get_principal)):
    ws = await get_ws(principal["workspace_id"])
    can_manage = "members:manage" in perms_for(principal["pack"])
    section_access = sec_access.normalize_section_access(ws.get("section_access"))
    depts = await workspace_departments(principal["workspace_id"], ws)
    mems = await db.memberships.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).to_list(200)
    members_out = []
    for m in mems:
        pack = pack_of(m)
        if pack == "owner":
            continue  # Owners/CEOs always have full access — not managed here
        u = await db.users.find_one({"user_id": m.get("user_id")}, {"_id": 0, "name": 1, "picture": 1}) if m.get("user_id") else None
        grants = sec_access.normalize_section_grants(m.get("section_grants"))
        from_pack = sec_access.sections_for_perms(perms_for(pack))
        dept = (m.get("department") or "General").strip()
        from_dept = [sid for sid, depts_map in section_access.items() if dept in (depts_map or [])]
        effective = sorted(set(from_pack) | set(grants) | set(from_dept))
        members_out.append({
            "membership_id": m["membership_id"],
            "email": m["email"],
            "name": (u or {}).get("name") or m["email"],
            "picture": (u or {}).get("picture"),
            "pack": pack,
            "department": dept,
            "status": m.get("status"),
            "section_grants": grants,
            "from_pack": from_pack,
            "from_department": from_dept,
            "effective": effective,
        })
    members_out.sort(key=lambda x: (x.get("name") or x["email"]).lower())
    return {
        "sections": sec_access.MANAGEABLE_SECTIONS,
        "departments": depts,
        "section_access": section_access,
        "members": members_out,
        "can_manage": can_manage,
    }


@api_router.patch("/access/sections")
async def update_section_access(payload: SectionAccessInput, principal=Depends(require_pro_perm("members:manage"))):
    """Legacy department → section map (kept for API compatibility). Prefer /access/member-grants."""
    normalized = sec_access.normalize_section_access(payload.section_access)
    await db.workspaces.update_one(
        {"workspace_id": principal["workspace_id"]},
        {"$set": {"section_access": normalized}},
    )
    return {"ok": True, "section_access": normalized}


@api_router.patch("/access/member-grants")
async def update_member_grants(payload: MemberGrantsInput, principal=Depends(require_pro_perm("members:manage"))):
    """CEO sets per-member section grants. Owners are ignored — they always have full access."""
    if not isinstance(payload.grants, dict):
        raise HTTPException(status_code=400, detail="grants must be an object")
    ws_id = principal["workspace_id"]
    updated = 0
    for membership_id, raw_grants in payload.grants.items():
        mid = str(membership_id).strip()
        if not mid:
            continue
        m = await db.memberships.find_one({"membership_id": mid, "workspace_id": ws_id}, {"_id": 0})
        if not m:
            continue
        if pack_of(m) == "owner":
            continue
        grants = sec_access.normalize_section_grants(raw_grants if isinstance(raw_grants, list) else [])
        await db.memberships.update_one(
            {"membership_id": mid, "workspace_id": ws_id},
            {"$set": {"section_grants": grants}},
        )
        updated += 1
    return {"ok": True, "updated": updated}


@api_router.delete("/members/{membership_id}")
async def remove_member(membership_id: str, principal=Depends(require_pro_perm("members:manage"))):
    m = await db.memberships.find_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.get("user_id") == principal["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    await db.memberships.delete_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]})
    await unlink_person_membership(principal["workspace_id"], membership_id)
    return {"ok": True}


# ------------------------- Company / module data -------------------------
@api_router.get("/company")
async def company(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return {
        "name": c["name"], "plan": c["plan"], "stage": c["stage"], "employees": c["employees"],
        "founded": c["founded"], "mission": c["mission"], "industry": c.get("industry", ""),
        "founder_title": c.get("founder_title", ""),
        "ceo_name": principal.get("name") or "CEO",
        "role": principal["role"], "workspace_id": c["workspace_id"],
        "onboarding_done": c.get("onboarding_done", True),
        "company_setup_done": c.get("company_setup_done", True),
        "template": c.get("template", "sample"),
    }


COMPANY_STAGES = frozenset({"Pre-seed", "Seed", "Series A", "Series B", "Growth", "Bootstrapped", "Other"})
FOUNDER_TITLES = frozenset({"CEO", "Founder", "Co-founder", "Managing Director", "President", "Other"})


class CompanySetupInput(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    stage: Optional[str] = None
    employees: Optional[int] = None
    founded: Optional[str] = None
    mission: Optional[str] = None
    founder_title: Optional[str] = None
    company_setup_done: bool = True


@api_router.patch("/company")
async def update_company(payload: CompanySetupInput, principal=Depends(require("workspace:edit"))):
    updates = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Company name is required")
        updates["name"] = name
    if payload.industry is not None:
        updates["industry"] = payload.industry.strip()[:120]
    if payload.stage is not None:
        stage = payload.stage.strip()
        if stage and stage not in COMPANY_STAGES:
            raise HTTPException(status_code=400, detail="Invalid company stage")
        updates["stage"] = stage or "Series A"
    if payload.employees is not None:
        if payload.employees < 0 or payload.employees > 100000:
            raise HTTPException(status_code=400, detail="Invalid team size")
        updates["employees"] = payload.employees
    if payload.founded is not None:
        founded = payload.founded.strip()
        if founded and (len(founded) != 4 or not founded.isdigit()):
            raise HTTPException(status_code=400, detail="Founded year must be YYYY")
        updates["founded"] = founded or "2022"
    if payload.mission is not None:
        updates["mission"] = payload.mission.strip()[:500]
    if payload.founder_title is not None:
        title = payload.founder_title.strip()
        if title and title not in FOUNDER_TITLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        updates["founder_title"] = title or "CEO"
    if payload.company_setup_done:
        updates["company_setup_done"] = True
    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": updates})
    return {"ok": True}


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
        await dept_migrate.migrate_workspace_sales_finance(db, ws_id)
        finance_dept_id = await dept_migrate.finance_department_id(db, ws_id)
        samples = sample_financial_entries(ws_id)
        if finance_dept_id:
            for e in samples:
                e["department_id"] = finance_dept_id
        await db.financial_entries.insert_many(samples)
    else:
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": {"onboarding_done": True}})
    return {"ok": True}


@api_router.get("/briefing")
async def briefing(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    # Lazy refresh of AI decision/delegate suggestions when stale (>24h)
    if _insights_stale(c) and helm_llm.anthropic_configured():
        try:
            await _generate_insights(c["workspace_id"], raise_on_rate_limit=False)
            c = await get_ws(principal["workspace_id"])
        except Exception:
            logger.exception("lazy insights generation failed for %s", c.get("workspace_id"))
    b = dict(c["briefing"])
    is_pro = workspace_is_pro(c)
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
    b["what_to_decide"] = _briefing_what_to_decide(c)
    b["what_to_delegate"] = _briefing_what_to_delegate(c)
    b["insights_generated_at"] = c.get("insights_generated_at")
    return {**b, "is_pro": is_pro, "ai_summary": b.get("ai_summary") if is_pro else None}


INSIGHTS_STALE_HOURS = 24
_IMPACT_RANK = {"High": 0, "Medium": 1, "Low": 2}


def _insights_stale(c: dict) -> bool:
    raw = c.get("insights_generated_at")
    if not raw:
        return True
    try:
        taken = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if taken.tzinfo is None:
            taken = taken.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - taken >= timedelta(hours=INSIGHTS_STALE_HOURS)


def _briefing_what_to_decide(c: dict) -> list:
    """Pending decisions + AI suggestions for the Briefing column."""
    items = []
    for d in c.get("decisions") or []:
        if d.get("status") != "pending":
            continue
        items.append({
            "id": d["id"],
            "title": d.get("title") or "Untitled",
            "detail": (d.get("recommendation") or d.get("description") or "").strip(),
            "urgency": "high" if d.get("impact") == "High" else "medium",
            "impact": d.get("impact") or "Medium",
            "due": d.get("due") or "",
            "source": d.get("source") or "manual",
            "confidence": d.get("confidence"),
        })
    for s in c.get("decision_suggestions") or []:
        if s.get("status") != "suggested":
            continue
        items.append({
            "id": s["id"],
            "title": s.get("title") or "Untitled",
            "detail": (s.get("recommendation") or s.get("description") or "").strip(),
            "urgency": "high" if s.get("impact") == "High" else "medium",
            "impact": s.get("impact") or "Medium",
            "due": s.get("due") or "",
            "source": "ai_suggested",
            "confidence": s.get("confidence"),
        })

    def sort_key(x):
        return (_IMPACT_RANK.get(x.get("impact"), 9), x.get("due") or "9999")

    items.sort(key=sort_key)
    return items[:5]


def _briefing_what_to_delegate(c: dict) -> list:
    out = []
    for s in c.get("delegate_suggestions") or []:
        if s.get("status") and s.get("status") != "suggested":
            continue
        out.append({
            "id": s["id"],
            "title": s.get("title") or "Untitled",
            "detail": s.get("detail") or "",
            "owner": s.get("suggested_owner_name") or "Unassigned",
            "suggested_owner_user_id": s.get("suggested_owner_user_id"),
            "suggested_owner_name": s.get("suggested_owner_name"),
            "source": "ai_suggested",
        })
        if len(out) >= 5:
            break
    return out


async def _recent_updates(workspace_id: str, days: int = 7) -> list:
    today = datetime.now(timezone.utc).date()
    day_list = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    return await db.updates.find(
        {"workspace_id": workspace_id, "day": {"$in": day_list}},
        {"_id": 0},
    ).to_list(500)


async def _generate_insights(workspace_id: str, *, raise_on_rate_limit: bool = True) -> dict:
    """Detect signals, draft AI suggestions, replace workspace suggestion lists."""
    if await doc_rate_limit.insights_over_limit(db, workspace_id):
        if raise_on_rate_limit:
            raise HTTPException(
                status_code=429,
                detail="Suggestion regeneration limit reached — try again tomorrow",
            )
        return {"skipped": "rate_limited"}

    if not helm_llm.anthropic_configured():
        if raise_on_rate_limit:
            raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
        return {"skipped": "ai_unconfigured"}

    c = await get_ws(workspace_id)
    fin = await compute_financials(workspace_id)
    currency = fin.get("currency") or "usd"
    entries = await db.financial_entries.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(5000)
    expense_by_month = decision_engine.expense_totals_by_month_category(entries)
    deals = await db.deals.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(500)
    tasks = list((c.get("tasks") or {}).get("items") or [])
    updates = await _recent_updates(workspace_id, days=7)
    signals = decision_engine.collect_signals(
        fin=fin,
        expense_by_month=expense_by_month,
        deals=deals,
        tasks=tasks,
        updates=updates,
        currency=currency,
    )
    company_context = {
        "name": c.get("name"),
        "stage": c.get("stage"),
        "employees": c.get("employees"),
        "mrr": fin.get("mrr"),
        "runway_months": fin.get("runway_months"),
        "burn": fin.get("burn"),
    }
    decision_suggestions = []
    delegate_suggestions = []
    now = datetime.now(timezone.utc).isoformat()
    for sig in signals:
        try:
            if sig.get("type") in decision_engine.DECISION_SIGNAL_TYPES:
                draft = await helm_llm.draft_decision(sig, company_context)
                decision_suggestions.append({
                    "id": f"sug_{uuid.uuid4().hex[:10]}",
                    "status": "suggested",
                    "source": "ai_suggested",
                    "signal_type": sig.get("type"),
                    "signal": sig,
                    "severity": sig.get("severity"),
                    "created_at": now,
                    **draft,
                    "due": "",
                    "owner": None,
                })
            elif sig.get("type") in decision_engine.DELEGATE_SIGNAL_TYPES:
                draft = await helm_llm.draft_delegate(sig, company_context)
                delegate_suggestions.append({
                    "id": f"del_{uuid.uuid4().hex[:10]}",
                    "status": "suggested",
                    "source": "ai_suggested",
                    "signal_type": sig.get("type"),
                    "signal": sig,
                    "severity": sig.get("severity"),
                    "created_at": now,
                    **draft,
                })
        except Exception:
            logger.exception("draft failed for signal %s", sig.get("type"))

    await doc_rate_limit.record_insights_event(db, workspace_id)
    await db.workspaces.update_one(
        {"workspace_id": workspace_id},
        {"$set": {
            "decision_suggestions": decision_suggestions,
            "delegate_suggestions": delegate_suggestions,
            "insights_generated_at": now,
        }},
    )
    notify = {"emailed": False, "slack": False, "new_alerts": 0}
    try:
        # Re-read workspace so notified_signal_ids / slack webhook are current
        c_fresh = await get_ws(workspace_id)
        notify = await _notify_high_severity_alerts(workspace_id, decision_suggestions, c_fresh)
    except Exception:
        logger.exception("high-severity notify failed (non-blocking)")
    return {
        "ok": True,
        "signals": len(signals),
        "decision_suggestions": len(decision_suggestions),
        "delegate_suggestions": len(delegate_suggestions),
        "insights_generated_at": now,
        "notifications": notify,
    }


@api_router.get("/activities")
async def list_activities(
    principal=Depends(get_principal),
    limit: int = Query(50, ge=1),
    before: Optional[str] = None,
):
    page_limit = clamp_limit(limit)
    ws = principal["workspace_id"]
    filt = apply_before_filter({"workspace_id": ws}, "created_at", before, id_field="activity_id")
    acts = await db.activities.find(filt, {"_id": 0}).sort([("created_at", -1), ("activity_id", -1)]).limit(page_limit).to_list(page_limit)
    for a in acts:
        a["ago"] = _rel_time(a["created_at"])
    cursor = next_cursor(acts, "created_at", page_limit, id_field="activity_id")
    return {"items": acts, "activities": acts, "next_cursor": cursor}


@api_router.get("/activities/export")
async def export_activities(
    start: str = Query(..., description="Start date YYYY-MM-DD (inclusive)"),
    end: str = Query(..., description="End date YYYY-MM-DD (inclusive)"),
    format: str = Query("csv"),
    principal=Depends(get_principal),
):
    """Owner/admin activity audit export. Non-admins get 403."""
    if "members:manage" not in perms_for(principal["pack"]):
        raise HTTPException(status_code=403, detail="Only workspace owners/admins can export the activity log")
    if (format or "csv").lower() != "csv":
        raise HTTPException(status_code=400, detail="Only format=csv is supported")
    try:
        start_d = datetime.strptime(start.strip()[:10], "%Y-%m-%d").date()
        end_d = datetime.strptime(end.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="start and end must be YYYY-MM-DD")
    if end_d < start_d:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    start_iso = datetime(start_d.year, start_d.month, start_d.day, tzinfo=timezone.utc).isoformat()
    end_exclusive = datetime(end_d.year, end_d.month, end_d.day, tzinfo=timezone.utc) + timedelta(days=1)
    end_iso = end_exclusive.isoformat()
    acts = await db.activities.find(
        {
            "workspace_id": principal["workspace_id"],
            "created_at": {"$gte": start_iso, "$lt": end_iso},
        },
        {"_id": 0},
    ).sort("created_at", 1).to_list(50000)

    import csv as csv_mod
    import io as io_mod
    buf = io_mod.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(["timestamp", "actor_name", "area", "action", "message"])
    for a in acts:
        writer.writerow([
            a.get("created_at") or "",
            a.get("actor_name") or "",
            a.get("module") or "",
            a.get("action") or "",
            a.get("summary") or "",
        ])
    data = buf.getvalue()
    filename = f"helm-activity-{start_d.isoformat()}-to-{end_d.isoformat()}.csv"
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.post("/briefing/generate")
async def generate_briefing(principal=Depends(require_pro_perm("briefing:generate"))):
    c = await get_ws(principal["workspace_id"])
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
    b = c["briefing"]
    context = {"company": c["name"], "metrics": b.get("what_to_decide"), "what_changed": b["what_changed"],
               "decisions": b["what_to_decide"], "financials": await compute_financials(c["workspace_id"])}
    cal_snap = await _google_calendar_snapshot(c)
    if cal_snap and cal_snap.get("meetings"):
        context["calendar_today"] = [
            {"time": m.get("time"), "title": m.get("title"), "duration": m.get("duration")}
            for m in cal_snap["meetings"][:8]
        ]
    system = ("You are Helm, an executive chief-of-staff AI for a startup CEO. Write a crisp morning briefing in 3-4 sentences. "
              "Synthesis over raw data, signal over noise. Lead with what matters most, name the single most important decision, "
              "and end with a confident recommendation. No fluff, no lists.")
    text = await helm_llm.complete(system, f"Company data for today:\n{json.dumps(context, indent=2)}\n\nWrite the CEO's morning briefing.")
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"briefing.ai_summary": text}})
    return {"ai_summary": text}


@api_router.get("/decisions")
async def decisions(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    suggestions = [s for s in (c.get("decision_suggestions") or []) if s.get("status") == "suggested"]
    return {
        "decisions": c["decisions"],
        "suggestions": suggestions,
        "insights_generated_at": c.get("insights_generated_at"),
        "is_pro": workspace_is_pro(c),
        "can_act": await can_section_write(principal, "decisions", "decisions:act"),
    }


class DecisionAction(BaseModel):
    action: str
    owner: Optional[str] = None


@api_router.post("/decisions/{decision_id}/action")
async def decision_action(decision_id: str, payload: DecisionAction, principal=Depends(require_section("decisions", "decisions:act"))):
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
    # Manual creates should not invent a confidence %; AI drafts set it explicitly.
    conf = None if p.confidence is None else max(0, min(100, int(p.confidence)))
    return {"title": p.title.strip(), "category": p.category.strip() or "General",
            "description": p.description.strip(), "recommendation": (p.recommendation or "").strip(),
            "confidence": conf, "due": p.due.strip() or "—",
            "impact": p.impact if p.impact in ("High", "Medium", "Low") else "Medium"}


@api_router.post("/decisions")
async def create_decision(payload: DecisionInput, principal=Depends(require_section("decisions", "decisions:act"))):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    d = {
        "id": f"d_{uuid.uuid4().hex[:8]}",
        "status": "pending",
        "owner": None,
        "source": "manual",
        **_decision_fields(payload),
    }
    # Manual form never sends a meaningful confidence — drop empty/zero noise
    if payload.confidence is None:
        d["confidence"] = None
    decisions = c["decisions"] + [d]
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    await log_activity(principal, "decisions", "decision.create", f"New decision: {d['title']}")
    return {"ok": True, "decision": d}


@api_router.post("/decisions/generate-suggestions")
async def generate_decision_suggestions(principal=Depends(require_section("decisions", "decisions:act"))):
    result = await _generate_insights(principal["workspace_id"], raise_on_rate_limit=True)
    c = await get_ws(principal["workspace_id"])
    return {
        **result,
        "suggestions": [s for s in (c.get("decision_suggestions") or []) if s.get("status") == "suggested"],
        "delegate_suggestions": [s for s in (c.get("delegate_suggestions") or []) if s.get("status") == "suggested"],
    }


@api_router.post("/decisions/suggestions/{suggestion_id}/approve")
async def approve_decision_suggestion(suggestion_id: str, principal=Depends(require_section("decisions", "decisions:act"))):
    c = await get_ws(principal["workspace_id"])
    suggestions = list(c.get("decision_suggestions") or [])
    sug = next((s for s in suggestions if s.get("id") == suggestion_id), None)
    if not sug or sug.get("status") != "suggested":
        raise HTTPException(status_code=404, detail="Suggestion not found")
    decision = {
        "id": f"d_{uuid.uuid4().hex[:8]}",
        "title": sug.get("title") or "Untitled",
        "category": sug.get("category") or "General",
        "description": sug.get("description") or "",
        "recommendation": sug.get("recommendation") or "",
        "confidence": sug.get("confidence"),
        "status": "pending",
        "owner": None,
        "due": sug.get("due") or "—",
        "impact": sug.get("impact") if sug.get("impact") in ("High", "Medium", "Low") else "Medium",
        "source": "ai_suggested",
        "from_suggestion_id": suggestion_id,
        "signal_type": sug.get("signal_type"),
    }
    decisions = list(c.get("decisions") or []) + [decision]
    suggestions = [s for s in suggestions if s.get("id") != suggestion_id]
    await db.workspaces.update_one(
        {"workspace_id": c["workspace_id"]},
        {"$set": {"decisions": decisions, "decision_suggestions": suggestions}},
    )
    await log_activity(principal, "decisions", "suggestion.approve", f"Accepted Helm suggestion: {decision['title']}")
    return {"ok": True, "decision": decision}


@api_router.post("/decisions/suggestions/{suggestion_id}/dismiss")
async def dismiss_decision_suggestion(suggestion_id: str, principal=Depends(require_section("decisions", "decisions:act"))):
    import alert_notify as an
    c = await get_ws(principal["workspace_id"])
    suggestions = list(c.get("decision_suggestions") or [])
    sug = next((s for s in suggestions if s.get("id") == suggestion_id), None)
    before = len(suggestions)
    suggestions = [s for s in suggestions if s.get("id") != suggestion_id]
    if len(suggestions) == before:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    # Allow re-notify if the same signal recurs after dismiss
    notified = list(c.get("notified_signal_ids") or [])
    if sug:
        key = an.signal_notify_key(sug.get("signal") or sug)
        notified = [k for k in notified if k != key]
    await db.workspaces.update_one(
        {"workspace_id": c["workspace_id"]},
        {"$set": {"decision_suggestions": suggestions, "notified_signal_ids": notified}},
    )
    return {"ok": True}


@api_router.post("/delegates/suggestions/{suggestion_id}/assign")
async def assign_delegate_suggestion(suggestion_id: str, principal=Depends(require_section("decisions", "decisions:act"))):
    """Promote a delegate suggestion into a real task assigned to the suggested owner."""
    c = await get_ws(principal["workspace_id"])
    suggestions = list(c.get("delegate_suggestions") or [])
    sug = next((s for s in suggestions if s.get("id") == suggestion_id), None)
    if not sug or (sug.get("status") and sug.get("status") != "suggested"):
        raise HTTPException(status_code=404, detail="Suggestion not found")
    t = c["tasks"]
    assignee_uid = sug.get("suggested_owner_user_id") or principal["user_id"]
    assignee_name = sug.get("suggested_owner_name") or principal.get("name") or "Me"
    if sug.get("suggested_owner_user_id"):
        member = await db.memberships.find_one(
            {"workspace_id": principal["workspace_id"], "user_id": sug["suggested_owner_user_id"], "status": "active"},
            {"_id": 0},
        )
        if member:
            u = await db.users.find_one({"user_id": sug["suggested_owner_user_id"]}, {"_id": 0, "name": 1})
            assignee_uid = sug["suggested_owner_user_id"]
            assignee_name = (u or {}).get("name") or member.get("email") or assignee_name
    item = {
        "id": f"t_{uuid.uuid4().hex[:8]}",
        "title": (sug.get("title") or "Follow up").strip()[:200],
        "assignee": assignee_name,
        "assignee_user_id": assignee_uid,
        "priority": "High" if (sug.get("signal") or {}).get("severity") == "high" else "Medium",
        "column": "backlog",
        "tag": "Delegated",
        "due": "",
        "progress": 0,
        "source": "ai_suggested",
        "from_suggestion_id": suggestion_id,
        "note": sug.get("detail") or "",
    }
    t["items"].append(item)
    suggestions = [s for s in suggestions if s.get("id") != suggestion_id]
    await db.workspaces.update_one(
        {"workspace_id": c["workspace_id"]},
        {"$set": {"tasks": t, "delegate_suggestions": suggestions}},
    )
    await log_activity(principal, "tasks", "delegate.assign", f"Assigned from Helm: {item['title']} → {assignee_name}")
    await notify_task_delegated(
        assignee_user_id=assignee_uid,
        previous_assignee_user_id=None,
        task=item,
        principal=principal,
        workspace_name=c.get("name") or "your company",
    )
    return {"ok": True, "task": item}


@api_router.post("/delegates/suggestions/{suggestion_id}/dismiss")
async def dismiss_delegate_suggestion(suggestion_id: str, principal=Depends(require_section("decisions", "decisions:act"))):
    c = await get_ws(principal["workspace_id"])
    suggestions = list(c.get("delegate_suggestions") or [])
    before = len(suggestions)
    suggestions = [s for s in suggestions if s.get("id") != suggestion_id]
    if len(suggestions) == before:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    await db.workspaces.update_one(
        {"workspace_id": c["workspace_id"]},
        {"$set": {"delegate_suggestions": suggestions}},
    )
    return {"ok": True}

@api_router.patch("/decisions/{decision_id}")
async def edit_decision(decision_id: str, payload: DecisionInput, principal=Depends(require_section("decisions", "decisions:act"))):
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
async def delete_decision(decision_id: str, principal=Depends(require_section("decisions", "decisions:act"))):
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
STAGE_LABEL = {"lead": "Lead", "qualified": "Qualified", "proposal": "Proposal",
               "negotiation": "Negotiation", "won": "Won", "lost": "Lost"}


def _deal_metrics(deals):
    open_deals = [d for d in deals if d["stage"] not in ("won", "lost")]
    by_stage = [{"stage": s, "label": STAGE_LABEL[s],
                 "count": len([d for d in deals if d["stage"] == s]),
                 "value": round(sum(d["value"] for d in deals if d["stage"] == s), 2)} for s in DEAL_STAGES]
    return {"open_value": round(sum(d["value"] for d in open_deals), 2),
            "won_value": round(sum(d["value"] for d in deals if d["stage"] == "won"), 2),
            "open_count": len(open_deals), "by_stage": by_stage}


async def _deal_metrics_for_workspace(workspace_id: str, department_ids: Optional[list] = None):
    """Aggregate pipeline metrics in MongoDB instead of loading all deals."""
    match = dept_access.apply_department_filter(
        {"workspace_id": workspace_id}, department_ids,
    )
    rows = await db.deals.aggregate([
        {"$match": match},
        {"$group": {"_id": "$stage", "count": {"$sum": 1}, "value": {"$sum": "$value"}}},
    ]).to_list(None)
    by_stage_map = {r["_id"]: r for r in rows}
    by_stage = []
    open_value = open_count = 0.0
    won_value = 0.0
    for s in DEAL_STAGES:
        row = by_stage_map.get(s, {"count": 0, "value": 0})
        count = int(row["count"])
        value = round(float(row["value"]), 2)
        by_stage.append({"stage": s, "label": STAGE_LABEL[s], "count": count, "value": value})
        if s not in ("won", "lost"):
            open_value += value
            open_count += count
        elif s == "won":
            won_value = value
    return {"open_value": round(open_value, 2),
            "won_value": round(won_value, 2), "open_count": int(open_count), "by_stage": by_stage}


class DealInput(BaseModel):
    name: str
    company: str = ""
    value: float = 0
    stage: str = "lead"
    owner_name: str = ""
    close_date: str = ""


@api_router.get("/deals")
async def list_deals(
    principal=Depends(get_principal),
    limit: int = Query(50, ge=1),
    before: Optional[str] = None,
):
    page_limit = clamp_limit(limit)
    ws = principal["workspace_id"]
    dept_ids = await dept_access.accessible_department_ids(db, principal, dept_catalog.TYPE_SALES)
    base = dept_access.apply_department_filter({"workspace_id": ws}, dept_ids)
    filt = apply_before_filter(base, "updated_at", before, id_field="id")
    deals = await db.deals.find(filt, {"_id": 0}).sort([("updated_at", -1), ("id", -1)]).limit(page_limit).to_list(page_limit)
    metrics = await _deal_metrics_for_workspace(ws, department_ids=dept_ids)
    cursor = next_cursor(deals, "updated_at", page_limit, id_field="id")
    currency = await _workspace_currency(ws)
    return {
        "items": deals,
        "deals": deals,
        "next_cursor": cursor,
        "can_write": await can_section_write(principal, "sales", "sales:write"),
        "metrics": metrics,
        "currency": currency,
        "currency_symbol": currency_symbol(currency),
        "stages": [{"id": s, "label": STAGE_LABEL[s]} for s in DEAL_STAGES],
    }


@api_router.post("/deals")
async def create_deal(payload: DealInput, principal=Depends(require_section("sales", "sales:write"))):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Deal name is required")
    stage = payload.stage if payload.stage in DEAL_STAGES else "lead"
    now = datetime.now(timezone.utc).isoformat()
    currency = await _workspace_currency(principal["workspace_id"])
    creator_name = (principal.get("name") or principal.get("email") or "").strip()
    sales_dept_id = await dept_migrate.sales_department_id(db, principal["workspace_id"])
    deal = {
        "id": f"deal_{uuid.uuid4().hex[:8]}",
        "workspace_id": principal["workspace_id"],
        "department_id": sales_dept_id,
        "name": payload.name.strip(),
        "company": payload.company.strip(),
        "value": round(payload.value, 2),
        "stage": stage,
        "owner_name": payload.owner_name.strip() or creator_name,
        "created_by_user_id": principal["user_id"],
        "created_by_name": creator_name,
        "close_date": payload.close_date.strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.deals.insert_one(dict(deal))
    await log_activity(principal, "sales", "deal.create",
                       f"New deal: {deal['name']} · {fmt_money(deal['value'], currency)} ({STAGE_LABEL[stage]})",
                       {"value": deal["value"], "stage": stage})
    return {"ok": True, "deal": deal}


@api_router.patch("/deals/{deal_id}")
async def update_deal(deal_id: str, payload: DealInput, principal=Depends(require_section("sales", "sales:write"))):
    d = await db.deals.find_one({"id": deal_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    stage = payload.stage if payload.stage in DEAL_STAGES else d["stage"]
    # created_by_* are set once at creation and never edited here
    upd = {"name": payload.name.strip() or d["name"], "company": payload.company.strip(),
           "value": round(payload.value, 2), "stage": stage,
           "owner_name": payload.owner_name.strip() or d.get("owner_name", ""),
           "close_date": payload.close_date.strip(), "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.deals.update_one({"id": deal_id, "workspace_id": principal["workspace_id"]}, {"$set": upd})
    if stage != d["stage"]:
        currency = await _workspace_currency(principal["workspace_id"])
        if stage == "won":
            summary = f"Won {upd['name']} · {fmt_money(upd['value'], currency)}"
        elif stage == "lost":
            summary = f"Lost {upd['name']}"
        else:
            summary = f"{upd['name']} moved to {STAGE_LABEL[stage]}"
        await log_activity(principal, "sales", "deal.stage", summary, {"stage": stage})
    # Return updated deal including immutable created_by fields
    updated = {**d, **upd}
    return {"ok": True, "deal": updated}


@api_router.delete("/deals/{deal_id}")
async def delete_deal(deal_id: str, principal=Depends(require_section("sales", "sales:write"))):
    await db.deals.delete_one({"id": deal_id, "workspace_id": principal["workspace_id"]})
    return {"ok": True}


@api_router.get("/telemetry")
async def telemetry(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    fin = await compute_financials(c["workspace_id"])
    items = c["tasks"]["items"]
    open_tasks = len([t for t in items if t.get("column") != "done"])
    headcount = c.get("employees") or len(c["people"]["people"])
    now = datetime.now(timezone.utc)
    kpis = []
    sources = []
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
        sources.append({"label": "Financials", "detail": "Live from your financial entries", "freshness": "live"})
    kpis += [
        {"label": "Headcount", "value": str(headcount), "delta": 0, "tone": "neutral", "spark": []},
        {"label": "Open Tasks", "value": str(open_tasks), "delta": 0, "tone": "neutral", "spark": []},
    ]
    sources.append({"label": "People & Tasks", "detail": "Headcount and open tasks from workspace data", "freshness": "live"})
    deals = await db.deals.find({"workspace_id": c["workspace_id"]}, {"_id": 0}).to_list(500)
    metrics = _deal_metrics(deals) if deals else None
    currency = fin.get("currency") or "usd"
    if metrics:
        kpis.append({"label": "Pipeline", "value": fmt_money(metrics["open_value"], currency),
                     "delta": 0, "tone": "neutral", "spark": []})
        sources.append({"label": "Pipeline", "detail": "Live from deals in your CRM board", "freshness": "live"})
    revenue_trend = [{"month": r["month"], "mrr": r["revenue"], "target": round(r["revenue"] * 1.03)}
                     for r in fin["revenue_series"]]
    funnel = []
    if metrics:
        funnel = [{"stage": row["label"], "value": row["count"]} for row in metrics["by_stage"] if row["count"] > 0]
    elif (c.get("telemetry") or {}).get("funnel"):
        funnel = c["telemetry"]["funnel"]
        sources.append({"label": "Sales Funnel", "detail": "Sample funnel — add deals for live pipeline stages", "freshness": "sample"})
    tel = c.get("telemetry") or {}
    manual = c.get("telemetry_manual") or {}
    risks = manual.get("risks") if manual.get("risks") is not None else (tel.get("risks") or [])
    if risks and not metrics and not manual.get("risks"):
        sources.append({"label": "Risks", "detail": "Sample risk radar — edit risks below or connect integrations", "freshness": "sample"})
    elif manual.get("risks"):
        sources.append({"label": "Risks", "detail": "Manually maintained risk radar", "freshness": "live"})
    qb = c.get("quickbooks_tokens")
    if qb:
        sources.append({"label": "QuickBooks", "detail": "Accounting sync when connected", "freshness": "hourly"})
    if c.get("google_tokens"):
        sources.append({"label": "Google Calendar", "detail": "Meeting load from your calendar", "freshness": "live"})
    can_write = await can_section_write(principal, "telemetry", "telemetry:write")
    return {
        "kpis": kpis, "revenue_trend": revenue_trend, "funnel": funnel, "risks": risks,
        "expense_breakdown": fin["expense_breakdown"],
        "data_as_of": now.isoformat(),
        "sources": sources,
        "can_write": can_write,
        "notes": manual.get("notes") or "",
    }


class TelemetryRiskInput(BaseModel):
    risks: list
    notes: Optional[str] = ""


@api_router.patch("/telemetry")
async def update_telemetry(payload: TelemetryRiskInput, principal=Depends(require_section("telemetry", "telemetry:write"))):
    c = await get_ws(principal["workspace_id"])
    cleaned = []
    for r in payload.risks[:20]:
        if not isinstance(r, dict):
            continue
        name = (r.get("name") or "").strip()
        if not name:
            continue
        cleaned.append({
            "id": r.get("id") or f"r_{uuid.uuid4().hex[:8]}",
            "name": name[:120],
            "likelihood": max(1, min(5, int(r.get("likelihood") or 3))),
            "impact": max(1, min(5, int(r.get("impact") or 3))),
            "category": (r.get("category") or "General").strip()[:40],
        })
    manual = {"risks": cleaned, "notes": (payload.notes or "").strip()[:1000]}
    await db.workspaces.update_one(
        {"workspace_id": c["workspace_id"]},
        {"$set": {"telemetry_manual": manual}},
    )
    await log_activity(principal, "telemetry", "telemetry.edit", f"Updated telemetry — {len(cleaned)} risk(s)")
    return {"ok": True, "risks": cleaned, "notes": manual["notes"]}


@api_router.get("/financials")
async def financials(principal=Depends(get_principal)):
    dept_ids = await dept_access.accessible_department_ids(
        db, principal, dept_catalog.TYPE_ACCOUNTING_FINANCE,
    )
    fin = await compute_financials(principal["workspace_id"], department_ids=dept_ids)
    entry_filt = dept_access.apply_department_filter(
        {"workspace_id": principal["workspace_id"]}, dept_ids,
    )
    entries = await db.financial_entries.find(entry_filt, {"_id": 0}).sort("month", -1).to_list(5000)
    return {**fin, "entries": entries,
            "can_write": await can_section_write(principal, "financials", "finance:write"),
            "can_manage": "integrations:manage" in perms_for(principal["pack"])}


class FinEntryInput(BaseModel):
    type: str
    category: str
    amount: float
    month: str
    recurring: bool = False
    recurrence: Optional[str] = None  # "monthly" | "annual" when recurring (expenses)
    note: Optional[str] = ""
    source_document_id: Optional[str] = None


def _fin_entry_recurrence(payload: "FinEntryInput") -> Optional[str]:
    import finance_recurrence as fin_recur
    return fin_recur.normalize_recurrence(payload.recurring, payload.recurrence, payload.type)


ALLOWED_DOC_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})
MAX_DOC_BYTES = 15 * 1024 * 1024


@api_router.post("/documents/upload")
async def upload_financial_document(
    file: UploadFile = File(...),
    principal=Depends(require_section("financials", "finance:write")),
):
    await _enforce_ai_extract_quota(principal)
    await _enforce_document_rate_limit(
        principal, "upload", doc_rate_limit.DOC_UPLOAD_HOURLY_LIMIT,
        "Upload limit reached — try again in a bit",
    )
    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed. Upload PDF, PNG, or JPEG.")
    data = await file.read()
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 15MB.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if not doc_storage.r2_configured():
        raise HTTPException(status_code=503, detail="Document storage is not configured")
    filename = (file.filename or "document").replace("/", "_").replace("\\", "_")[:200]
    try:
        storage_key = await asyncio.to_thread(
            doc_storage.upload_document,
            principal["workspace_id"], data, filename, file.content_type,
        )
    except Exception as exc:
        logger.exception("document upload failed")
        raise HTTPException(status_code=500, detail="Could not store document") from exc
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": doc_id,
        "workspace_id": principal["workspace_id"],
        "storage_key": storage_key,
        "filename": filename,
        "content_type": file.content_type,
        "uploaded_by": principal["user_id"],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "uploaded",
        "extracted_data": None,
        "linked_entry_id": None,
    }
    await db.documents.insert_one(doc)
    await doc_rate_limit.record_event(db, principal["workspace_id"], "upload")
    await log_activity(principal, "financials", "document.upload", f"Uploaded bill · {filename}")
    return {"document_id": doc_id, "status": "uploaded"}


@api_router.post("/documents/{document_id}/extract")
async def extract_financial_document_route(
    document_id: str,
    force: bool = Query(False),
    principal=Depends(require_section("financials", "finance:write")),
):
    doc = await db.documents.find_one(
        {"id": document_id, "workspace_id": principal["workspace_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if (
        not force
        and doc.get("status") == "extracted"
        and doc.get("extracted_data")
    ):
        return doc["extracted_data"]
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI extraction is not configured")
    await _enforce_ai_extract_quota(principal)
    await _enforce_document_rate_limit(
        principal, "extract", doc_rate_limit.DOC_EXTRACT_HOURLY_LIMIT,
        "Extraction limit reached — try again in a bit",
    )
    try:
        file_bytes = await asyncio.to_thread(doc_storage.get_document_bytes, doc["storage_key"])
        extracted = await helm_llm.extract_financial_document(file_bytes, doc["content_type"])
        await doc_rate_limit.record_event(db, principal["workspace_id"], "extract")
        status = "failed" if extracted.get("error") in ("not_financial", "unparseable_amount") else "extracted"
        await db.documents.update_one(
            {"id": document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": status, "extracted_data": extracted}},
        )
        if status == "extracted":
            period = plan_usage.current_usage_period(await get_ws(principal["workspace_id"]))
            await plan_usage.increment_period_extract(db, principal["workspace_id"], period["key"])
            await log_activity(
                principal, "financials", "document.extract",
                f"Extracted bill data · {doc['filename']}",
            )
        return extracted
    except ValueError as exc:
        await db.documents.update_one(
            {"id": document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": "failed", "extracted_data": {"error": "parse_failed"}}},
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("document extract failed for %s", document_id)
        await db.documents.update_one(
            {"id": document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": "failed", "extracted_data": {"error": "extract_failed"}}},
        )
        raise HTTPException(status_code=500, detail="Could not extract document") from exc


@api_router.get("/documents/{document_id}")
async def get_financial_document(
    document_id: str,
    principal=Depends(require_section("financials", "finance:write")),
):
    doc = await db.documents.find_one(
        {"id": document_id, "workspace_id": principal["workspace_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        presigned_url = await asyncio.to_thread(doc_storage.get_presigned_url, doc["storage_key"])
    except Exception as exc:
        logger.exception("presigned url failed for %s", document_id)
        raise HTTPException(status_code=500, detail="Could not generate document URL") from exc
    return {**doc, "presigned_url": presigned_url}


@api_router.post("/financials/entries")
async def add_fin_entry(payload: FinEntryInput, principal=Depends(require_section("financials", "finance:write"))):
    if payload.type not in ("revenue", "expense"):
        raise HTTPException(status_code=400, detail="type must be revenue or expense")
    if not _valid_fin_month(payload.month):
        raise HTTPException(status_code=400, detail="month must be a valid YYYY-MM")
    if payload.amount < 0:
        raise HTTPException(status_code=400, detail="amount must be non-negative")
    source = "manual"
    source_document_id = None
    if source_document_id:
        # Atomic claim: only transition uploaded/extracted → committing once
        from pymongo import ReturnDocument
        claim = await db.documents.find_one_and_update(
            {
                "id": payload.source_document_id,
                "workspace_id": principal["workspace_id"],
                "status": {"$in": ["uploaded", "extracted"]},
            },
            {"$set": {"status": "committing"}},
            return_document=ReturnDocument.AFTER,
        )
        if not claim:
            src_doc = await db.documents.find_one(
                {"id": payload.source_document_id, "workspace_id": principal["workspace_id"]}, {"_id": 0},
            )
            if not src_doc:
                raise HTTPException(status_code=400, detail="Source document not found")
            raise HTTPException(status_code=400, detail="Document already committed to an entry")
        source = "ai_upload"
        source_document_id = payload.source_document_id
    finance_dept_id = await dept_migrate.finance_department_id(db, principal["workspace_id"])
    entry = {"id": f"fe_{uuid.uuid4().hex[:10]}", "workspace_id": principal["workspace_id"],
             "department_id": finance_dept_id,
             "type": payload.type, "category": payload.category.strip() or "Other",
             "amount": round(payload.amount, 2), "month": payload.month.strip(), "recurring": payload.recurring,
             "recurrence": _fin_entry_recurrence(payload),
             "note": (payload.note or "").strip(), "source": source, "created_by": principal["user_id"],
             "created_at": datetime.now(timezone.utc).isoformat()}
    if source_document_id:
        entry["source_document_id"] = source_document_id
    await db.financial_entries.insert_one(entry)
    entry.pop("_id", None)
    if source_document_id:
        await db.documents.update_one(
            {"id": source_document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": "committed", "linked_entry_id": entry["id"]}},
        )
    await log_activity(principal, "financials", "entry.add",
                       f"Logged {payload.type} · {entry['category']} {fmt_money(entry['amount'], await _workspace_currency(principal['workspace_id']))} ({payload.month})",
                       {"type": payload.type, "amount": entry["amount"], "month": payload.month})
    return {"ok": True, "entry": entry}


@api_router.patch("/financials/entries/{entry_id}")
async def edit_fin_entry(entry_id: str, payload: FinEntryInput, principal=Depends(require_section("financials", "finance:write"))):
    if payload.type not in ("revenue", "expense"):
        raise HTTPException(status_code=400, detail="type must be revenue or expense")
    if not _valid_fin_month(payload.month):
        raise HTTPException(status_code=400, detail="month must be a valid YYYY-MM")
    if payload.amount < 0:
        raise HTTPException(status_code=400, detail="amount must be non-negative")
    res = await db.financial_entries.update_one(
        {"id": entry_id, "workspace_id": principal["workspace_id"]},
        {"$set": {"type": payload.type, "category": payload.category.strip() or "Other",
                  "amount": round(payload.amount, 2), "month": payload.month.strip(),
                  "recurring": payload.recurring, "recurrence": _fin_entry_recurrence(payload),
                  "note": (payload.note or "").strip()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    await log_activity(principal, "financials", "entry.edit",
                       f"Updated a {payload.type} entry · {payload.category.strip() or 'Other'} ({payload.month})")
    return {"ok": True}


@api_router.delete("/financials/entries/{entry_id}")
async def delete_fin_entry(entry_id: str, principal=Depends(require_section("financials", "finance:write"))):
    doc = await db.financial_entries.find_one({"id": entry_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    await db.financial_entries.delete_one({"id": entry_id, "workspace_id": principal["workspace_id"]})
    if doc:
        await log_activity(principal, "financials", "entry.delete",
                           f"Removed a {doc.get('type')} entry · {doc.get('category')} ({doc.get('month')})")
    return {"ok": True}


class FinSettingsInput(BaseModel):
    cash: float
    gross_margin: Optional[float] = None
    currency: Optional[str] = None


@api_router.put("/financials/settings")
async def update_fin_settings(payload: FinSettingsInput, principal=Depends(require_section("financials", "finance:write"))):
    currency = normalize_currency(payload.currency) if payload.currency is not None else None
    sets = {
        "financial_settings.cash": round(payload.cash, 2),
        "financial_settings.gross_margin": payload.gross_margin,
    }
    if currency is not None:
        sets["financial_settings.currency"] = currency
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": sets})
    fin = await compute_financials(principal["workspace_id"])
    runway = fin["runway_months"]
    cur = fin.get("currency") or "usd"
    await log_activity(principal, "financials", "settings.update",
                       f"Updated cash to {fmt_money(payload.cash, cur)}" + (f" — runway now {runway}mo" if runway else ""),
                       {"cash": payload.cash, "runway_months": runway, "currency": cur})
    return {"ok": True, "settings": fin.get("settings"), "currency": cur}


class CsvImportConfirmInput(BaseModel):
    entries: list


@api_router.post("/financials/import-csv")
async def import_financials_csv_preview(
    file: UploadFile = File(...),
    principal=Depends(require_section("financials", "finance:write")),
):
    """Parse + validate CSV; return preview without writing to financial_entries."""
    import finance_csv as fin_csv
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV too large (max 5MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode CSV as UTF-8 or Latin-1")
    try:
        parsed = fin_csv.parse_financial_csv(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("csv parse failed")
        raise HTTPException(status_code=400, detail="Malformed CSV — check headers and row formatting")
    return {
        "ok": True,
        "preview": True,
        "committed": False,
        "filename": file.filename,
        **parsed,
    }


@api_router.post("/financials/import-csv/confirm")
async def import_financials_csv_confirm(
    payload: CsvImportConfirmInput,
    principal=Depends(require_section("financials", "finance:write")),
):
    """Bulk-insert previously previewed valid rows with source=csv_import."""
    if not payload.entries:
        raise HTTPException(status_code=400, detail="No entries to import")
    if len(payload.entries) > 5000:
        raise HTTPException(status_code=400, detail="Too many rows (max 5000)")
    now = datetime.now(timezone.utc).isoformat()
    finance_dept_id = await dept_migrate.finance_department_id(db, principal["workspace_id"])
    docs = []
    for raw in payload.entries:
        if not isinstance(raw, dict):
            continue
        entry_type = (raw.get("type") or "").strip().lower()
        if entry_type not in ("revenue", "expense"):
            continue
        try:
            amount = round(float(raw.get("amount")), 2)
        except (TypeError, ValueError):
            continue
        if amount < 0:
            continue
        month = (raw.get("month") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}", month) or not _valid_fin_month(month):
            continue
        docs.append({
            "id": f"fe_{uuid.uuid4().hex[:10]}",
            "workspace_id": principal["workspace_id"],
            "department_id": finance_dept_id,
            "type": entry_type,
            "category": (raw.get("category") or "Other").strip() or "Other",
            "amount": amount,
            "month": month,
            "recurring": bool(raw.get("recurring")),
            "recurrence": None,
            "note": (raw.get("note") or "").strip(),
            "source": "csv_import",
            "created_by": principal["user_id"],
            "created_at": now,
        })
    if not docs:
        raise HTTPException(status_code=400, detail="No valid entries to import")
    await db.financial_entries.insert_many(docs)
    for d in docs:
        d.pop("_id", None)
    await log_activity(
        principal, "financials", "entry.import",
        f"Imported {len(docs)} entr{'y' if len(docs) == 1 else 'ies'} from CSV",
        {"count": len(docs), "source": "csv_import"},
    )
    return {"ok": True, "committed": True, "imported_count": len(docs), "entries": docs}


@api_router.get("/tasks")
async def tasks(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    t = _normalize_task_columns(dict(c["tasks"]))
    t["can_create"] = "tasks:create" in perms_for(principal["pack"])
    t["can_assign"] = await can_section_write(principal, "tasks", "tasks:assign")
    t["my_user_id"] = principal["user_id"]
    return t


@api_router.get("/tasks/me")
async def my_tasks(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    items = [t for t in c["tasks"]["items"] if t.get("assignee_user_id") == principal["user_id"]]
    return {"items": items, "columns": _normalize_task_columns(c["tasks"])["columns"]}


class TaskInput(BaseModel):
    title: str
    priority: str = "Medium"
    tag: str = "General"
    due: str = ""
    column: str = "backlog"
    assignee_user_id: Optional[str] = None


@api_router.post("/tasks")
async def create_task(payload: TaskInput, principal=Depends(require_pro_perm("tasks:create"))):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    t = c["tasks"]
    assignee_uid = principal["user_id"]
    assignee_name = principal.get("name") or principal.get("email") or "Me"
    if payload.assignee_user_id and payload.assignee_user_id != principal["user_id"]:
        if not await can_section_write(principal, "tasks", "tasks:assign"):
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
    if item["column"] == "done":
        item["progress"] = 100
        item["done_at"] = datetime.now(timezone.utc).isoformat()
    t["items"].append(item)
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"tasks": t}})
    await notify_task_delegated(
        assignee_user_id=assignee_uid,
        previous_assignee_user_id=None,
        task=item,
        principal=principal,
        workspace_name=c.get("name") or "your company",
    )
    return {"ok": True, "task": item}


class TaskPatch(BaseModel):
    column: Optional[str] = None
    assignee_user_id: Optional[str] = None


@api_router.patch("/tasks/{task_id}")
async def patch_task(task_id: str, payload: TaskPatch, principal=Depends(require_pro_perm("tasks:move"))):
    c = await get_ws(principal["workspace_id"])
    t = c["tasks"]
    target = next((i for i in t["items"] if i["id"] == task_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Task not found")
    owns = target.get("assignee_user_id") == principal["user_id"]
    if target.get("assignee_user_id") and not owns and not await can_section_write(principal, "tasks", "tasks:assign"):
        raise HTTPException(status_code=403, detail="You can only move your own tasks")

    fields = payload.model_dump(exclude_unset=True)
    prev_assignee = target.get("assignee_user_id")

    if "column" in fields and fields["column"] is not None:
        prev_col = target.get("column")
        target["column"] = fields["column"]
        if fields["column"] == "done":
            target["progress"] = 100
            if prev_col != "done" or not target.get("done_at"):
                target["done_at"] = datetime.now(timezone.utc).isoformat()
        elif prev_col == "done":
            target.pop("done_at", None)

    if "assignee_user_id" in fields:
        if not await can_section_write(principal, "tasks", "tasks:assign"):
            raise HTTPException(status_code=403, detail="You cannot reassign tasks")
        new_uid = (fields["assignee_user_id"] or "").strip() or None
        if new_uid:
            member = await db.memberships.find_one(
                {"workspace_id": principal["workspace_id"], "user_id": new_uid, "status": "active"},
                {"_id": 0},
            )
            if not member:
                raise HTTPException(status_code=404, detail="Assignee is not in this workspace")
            u = await db.users.find_one({"user_id": new_uid}, {"_id": 0, "name": 1})
            target["assignee_user_id"] = new_uid
            target["assignee"] = (u or {}).get("name") or member.get("email") or "Teammate"
        else:
            target["assignee_user_id"] = principal["user_id"]
            target["assignee"] = principal.get("name") or principal.get("email") or "Me"

    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"tasks": t}})
    if "assignee_user_id" in fields:
        await notify_task_delegated(
            assignee_user_id=target.get("assignee_user_id"),
            previous_assignee_user_id=prev_assignee,
            task=target,
            principal=principal,
            workspace_name=c.get("name") or "your company",
        )
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
async def post_update(payload: UpdateInput, principal=Depends(require_pro_perm("updates:write"))):
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


# ------------------------- Private notes (My Day) -------------------------
NOTE_COLORS = ("gold", "sky", "emerald", "rose", "violet", "amber")


class NoteInput(BaseModel):
    text: str
    color: str = "gold"


@api_router.get("/notes")
async def list_notes(principal=Depends(get_principal)):
    notes = await db.private_notes.find(
        {"workspace_id": principal["workspace_id"], "user_id": principal["user_id"]},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(100)
    return {"notes": notes}


@api_router.post("/notes")
async def create_note(payload: NoteInput, principal=Depends(get_principal)):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Note text is required")
    now = datetime.now(timezone.utc).isoformat()
    color = payload.color if payload.color in NOTE_COLORS else "gold"
    doc = {
        "note_id": f"note_{uuid.uuid4().hex[:10]}",
        "workspace_id": principal["workspace_id"],
        "user_id": principal["user_id"],
        "text": payload.text.strip()[:800],
        "color": color,
        "created_at": now,
        "updated_at": now,
    }
    await db.private_notes.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "note": doc}


@api_router.patch("/notes/{note_id}")
async def edit_note(note_id: str, payload: NoteInput, principal=Depends(get_principal)):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Note text is required")
    now = datetime.now(timezone.utc).isoformat()
    color = payload.color if payload.color in NOTE_COLORS else None
    upd = {"text": payload.text.strip()[:800], "updated_at": now}
    if color:
        upd["color"] = color
    res = await db.private_notes.update_one(
        {"note_id": note_id, "workspace_id": principal["workspace_id"], "user_id": principal["user_id"]},
        {"$set": upd},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


@api_router.delete("/notes/{note_id}")
async def delete_note(note_id: str, principal=Depends(get_principal)):
    res = await db.private_notes.delete_one(
        {"note_id": note_id, "workspace_id": principal["workspace_id"], "user_id": principal["user_id"]},
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


def _parse_iso_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _shipped_in_window(items, *, now: Optional[datetime] = None, days: int = 7) -> int:
    """Count tasks that entered done within the last `days` (requires done_at)."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    n = 0
    for t in items:
        if t.get("column") != "done":
            continue
        done_at = _parse_iso_dt(t.get("done_at"))
        if done_at is not None and done_at >= cutoff:
            n += 1
    return n


def _signed_delta(curr, prev, *, money: bool = False, suffix: str = "", currency: str = "usd") -> str:
    if prev is None and curr is None:
        return "first week — no trend yet"
    if prev is None:
        return "first week — no trend yet"
    try:
        delta = float(curr if curr is not None else 0) - float(prev if prev is not None else 0)
    except (TypeError, ValueError):
        return "first week — no trend yet"
    if abs(delta) < 0.05:
        return f"flat vs last week{suffix}"
    sign = "+" if delta > 0 else ""
    if money:
        return f"{sign}{fmt_money(delta, currency)} vs last week{suffix}"
    if float(delta).is_integer():
        return f"{sign}{int(delta)} vs last week{suffix}"
    return f"{sign}{delta:.1f} vs last week{suffix}"


def _report_metric_snapshot(fin, items, ups, headcount) -> dict:
    return {
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "mrr": int(fin.get("mrr_value") or 0),
        "arr": int(fin.get("mrr_value") or 0) * 12,
        "runway_months": fin.get("runway_months"),
        "burn": int(fin.get("burn_value") or 0),
        "headcount": int(headcount or 0),
        "updates_count": len(ups or []),
        "blocked_count": len([u for u in (ups or []) if u.get("blocker")]),
        "shipped_week": _shipped_in_window(items or []),
        "open_tasks": len([t for t in (items or []) if t.get("column") != "done"]),
        "in_progress": len([t for t in (items or []) if t.get("column") == "in_progress"]),
    }


async def _apply_report_snapshot(workspace_id: str, current: dict) -> Optional[dict]:
    """Lazy weekly snapshot: return prior baseline for diffs; rotate when ≥7 days old or missing."""
    c = await get_ws(workspace_id)
    prior = c.get("report_snapshot")
    now = datetime.now(timezone.utc)
    taken = _parse_iso_dt((prior or {}).get("taken_at")) if prior else None
    rotate = prior is None or taken is None or (now - taken) >= timedelta(days=7)
    if rotate:
        await db.workspaces.update_one(
            {"workspace_id": workspace_id},
            {"$set": {"report_snapshot": current}},
        )
        # First store has no prior trend; subsequent weekly rotations diff against the old snap.
        return prior if (prior and taken is not None) else None
    return prior


def _computed_report_cards(c, fin, items, ups, headcount, prior=None):
    curr = _report_metric_snapshot(fin, items, ups, headcount)
    first_week = prior is None
    period = "First week" if first_week else "Vs last week"
    currency = fin.get("currency") or "usd"

    mrr_trend = _signed_delta(curr["mrr"], None if first_week else prior.get("mrr"), money=True, currency=currency)
    runway_trend = _signed_delta(
        curr["runway_months"],
        None if first_week else prior.get("runway_months"),
        suffix=" mo",
    )
    burn_trend = _signed_delta(curr["burn"], None if first_week else prior.get("burn"), money=True, currency=currency)
    hc_trend = _signed_delta(curr["headcount"], None if first_week else prior.get("headcount"))
    updates_trend = _signed_delta(curr["updates_count"], None if first_week else prior.get("updates_count"))
    blocked_trend = _signed_delta(curr["blocked_count"], None if first_week else prior.get("blocked_count"))
    shipped_trend = _signed_delta(curr["shipped_week"], None if first_week else prior.get("shipped_week"))

    if first_week:
        fin_summary = (
            f"MRR {fin['mrr']} · runway {fin['runway_months'] or '—'}mo · burn {fin['burn']} — "
            f"first week — no trend yet."
        )
        team_summary = (
            f"{curr['headcount']} people · {curr['updates_count']} update(s) today · "
            f"{curr['blocked_count']} blocked — first week — no trend yet."
        )
        exec_summary = (
            f"{curr['shipped_week']} shipped this week · {curr['in_progress']} in progress · "
            f"{curr['open_tasks']} open — first week — no trend yet."
        )
    else:
        fin_summary = f"MRR {mrr_trend} · runway {runway_trend} · burn {burn_trend}."
        team_summary = f"Headcount {hc_trend} · updates {updates_trend} · blocked {blocked_trend}."
        exec_summary = (
            f"Shipped this week {curr['shipped_week']} ({shipped_trend}) · "
            f"{curr['in_progress']} in progress · {curr['open_tasks']} open."
        )

    return [
        {"id": "auto_fin", "title": "Financial Snapshot", "type": "Finance", "period": period,
         "summary": fin_summary,
         "metrics": [
             {"label": "MRR", "value": fin["mrr"] if first_week else mrr_trend},
             {"label": "Runway", "value": (f"{fin['runway_months']}mo" if fin["runway_months"] else "—") if first_week else runway_trend},
             {"label": "Burn", "value": fin["burn"] if first_week else burn_trend},
         ],
         "source": "auto"},
        {"id": "auto_team", "title": "Team Pulse", "type": "People", "period": period,
         "summary": team_summary,
         "metrics": [
             {"label": "Headcount", "value": str(curr["headcount"]) if first_week else hc_trend},
             {"label": "Updates", "value": str(curr["updates_count"]) if first_week else updates_trend},
             {"label": "Blocked", "value": str(curr["blocked_count"]) if first_week else blocked_trend},
         ],
         "source": "auto"},
        {"id": "auto_exec", "title": "Execution", "type": "Delivery", "period": period,
         "summary": exec_summary,
         "metrics": [
             {"label": "Shipped", "value": str(curr["shipped_week"]) if first_week else f"{curr['shipped_week']} ({shipped_trend})"},
             {"label": "In progress", "value": str(curr["in_progress"])},
             {"label": "Open", "value": str(curr["open_tasks"])},
         ],
         "source": "auto"},
    ]


@api_router.get("/reports")
async def reports(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    fin = await compute_financials(c["workspace_id"])
    items = c["tasks"]["items"]
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": c["workspace_id"], "day": day}, {"_id": 0}).to_list(200)
    headcount = c.get("employees") or len(c["people"]["people"])
    manual = list(c.get("manual_reports") or [])
    current = _report_metric_snapshot(fin, items, ups, headcount)
    prior = await _apply_report_snapshot(c["workspace_id"], current)
    auto = _computed_report_cards(c, fin, items, ups, headcount, prior=prior)
    can_write = await can_section_write(principal, "reports", "reports:write")
    return {
        "reports": manual + auto,
        "manual_reports": manual,
        "auto_reports": auto,
        "can_write": can_write,
        "is_pro": workspace_is_pro(c),
    }


class ReportInput(BaseModel):
    title: str
    type: str = "General"
    period: str = ""
    summary: str = ""
    metrics: list = []


@api_router.post("/reports")
async def create_report(payload: ReportInput, principal=Depends(require_section("reports", "reports:write"))):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    manual = list(c.get("manual_reports") or [])
    report = {
        "id": f"rep_{uuid.uuid4().hex[:10]}",
        "title": payload.title.strip(),
        "type": (payload.type or "General").strip(),
        "period": (payload.period or "Manual").strip(),
        "summary": payload.summary.strip(),
        "metrics": payload.metrics[:6] if payload.metrics else [],
        "source": "manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    manual.append(report)
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"manual_reports": manual}})
    await log_activity(principal, "reports", "report.create", f"Added report: {report['title']}")
    return {"ok": True, "report": report}


@api_router.patch("/reports/{report_id}")
async def edit_report(report_id: str, payload: ReportInput, principal=Depends(require_section("reports", "reports:write"))):
    c = await get_ws(principal["workspace_id"])
    manual = list(c.get("manual_reports") or [])
    found = None
    for r in manual:
        if r["id"] == report_id:
            r.update({
                "title": payload.title.strip() or r["title"],
                "type": (payload.type or r.get("type", "General")).strip(),
                "period": (payload.period or r.get("period", "Manual")).strip(),
                "summary": payload.summary.strip() if payload.summary is not None else r.get("summary", ""),
                "metrics": payload.metrics if payload.metrics is not None else r.get("metrics", []),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            found = r
            break
    if not found:
        raise HTTPException(status_code=404, detail="Report not found")
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"manual_reports": manual}})
    return {"ok": True, "report": found}


@api_router.delete("/reports/{report_id}")
async def delete_report(report_id: str, principal=Depends(require_section("reports", "reports:write"))):
    c = await get_ws(principal["workspace_id"])
    manual = [r for r in (c.get("manual_reports") or []) if r["id"] != report_id]
    if len(manual) == len(c.get("manual_reports") or []):
        raise HTTPException(status_code=404, detail="Report not found")
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"manual_reports": manual}})
    return {"ok": True}


def _build_weekly_pack_context(c, fin, items, ups, headcount, prior=None) -> dict:
    """Assemble LLM context: manual reports + week-over-week trend cards."""
    manual = list(c.get("manual_reports") or [])
    auto = _computed_report_cards(c, fin, items, ups, headcount, prior=prior)
    return {
        "company": c["name"],
        "financials": fin,
        "kpis": (c.get("telemetry") or {}).get("kpis") or [],
        "reports": [{"title": r["title"], "summary": r["summary"]} for r in manual],
        "trends": [{"title": r["title"], "summary": r["summary"], "metrics": r.get("metrics")} for r in auto],
    }


@api_router.post("/reports/weekly-pack")
async def weekly_pack(principal=Depends(require_pro_perm("reports:pack"))):
    c = await get_ws(principal["workspace_id"])
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
    fin = await compute_financials(c["workspace_id"])
    items = c["tasks"]["items"]
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": c["workspace_id"], "day": day}, {"_id": 0}).to_list(200)
    headcount = c.get("employees") or len(c["people"]["people"])
    prior = c.get("report_snapshot")
    taken = _parse_iso_dt((prior or {}).get("taken_at")) if prior else None
    baseline = prior if taken else None
    context = _build_weekly_pack_context(c, fin, items, ups, headcount, prior=baseline)
    system = ("You are Helm, writing the Weekly CEO Pack. Produce a board-ready weekly summary in markdown with sections: "
              "Headline, Growth, Financial Health, Risks, and This Week's Focus. Be concise, executive, and specific. "
              "Use both manual reports and the week-over-week trend cards.")
    text = await helm_llm.complete(system, f"Data:\n{json.dumps(context, indent=2)}\n\nWrite the Weekly CEO Pack.")
    return {"content": text}


async def _google_calendar_snapshot(workspace: dict, week_start: Optional[datetime] = None) -> Optional[dict]:
    """Fetch Google Calendar events for a week when connected; None if not connected."""
    tokens = workspace.get("google_tokens")
    if not tokens:
        return None
    if week_start is None:
        week_start = _calendar_week_start(datetime.now(timezone.utc).date())
    try:
        events, refreshed = await gcal.fetch_week_calendar(
            tokens, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, week_start,
        )
        if refreshed is not tokens:
            await db.workspaces.update_one(
                {"workspace_id": workspace["workspace_id"]},
                {"$set": {"google_tokens": refreshed}},
            )
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        meetings = [e for e in events if e.get("date") == today_str and not e.get("all_day")]
        focus_hours, meeting_hours = gcal._compute_hours(meetings)
        return {
            "events": events,
            "meetings": meetings,
            "focus_hours": focus_hours,
            "meeting_hours": meeting_hours,
            "live": True,
            "source": "google_calendar",
            "week_start": week_start.strftime("%Y-%m-%d"),
        }
    except gcal.GoogleAuthError as exc:
        logger.warning("Google Calendar auth failed for %s: %s", workspace.get("workspace_id"), exc)
        await db.workspaces.update_one(
            {"workspace_id": workspace["workspace_id"]},
            {"$set": {"google_tokens": None}},
        )
        return {"events": [], "meetings": [], "focus_hours": 0, "meeting_hours": 0, "live": False, "auth_error": str(exc)}
    except Exception:
        logger.exception("Google Calendar fetch failed for %s", workspace.get("workspace_id"))
        return None


def _calendar_week_start(day) -> datetime:
    """Week starts Sunday (matches Helm calendar UI)."""
    sunday_offset = (day.weekday() + 1) % 7
    start = day - timedelta(days=sunday_offset)
    return datetime(start.year, start.month, start.day, tzinfo=timezone.utc)


def _normalize_seed_events(meetings: list[dict], day) -> list[dict]:
    day_str = day.isoformat()
    out = []
    for m in meetings:
        if m.get("start_at"):
            out.append(dict(m))
            continue
        parts = (m.get("time") or "09:00").split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
        duration = int(m.get("duration") or 30)
        end = start + timedelta(minutes=duration)
        row = dict(m)
        row.update({
            "date": day_str,
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "all_day": False,
        })
        out.append(row)
    return out


def _deadlines_as_events(upcoming: list[dict]) -> list[dict]:
    events = []
    for u in upcoming:
        events.append({
            "id": f"deadline_{u['id']}",
            "title": u["title"],
            "time": "",
            "duration": 0,
            "attendees": 0,
            "type": u.get("type", "Deadline"),
            "prep": None,
            "importance": "medium",
            "source": "helm",
            "date": u["date"],
            "start_at": f"{u['date']}T00:00:00+00:00",
            "end_at": f"{u['date']}T23:59:59+00:00",
            "all_day": True,
        })
    return events


@api_router.get("/calendar")
async def calendar(
    principal=Depends(get_principal),
    week_start: Optional[str] = Query(None, description="Sunday of the week to load (YYYY-MM-DD)"),
):
    c = await get_ws(principal["workspace_id"])
    if week_start:
        try:
            anchor_day = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="week_start must be YYYY-MM-DD")
    else:
        anchor_day = datetime.now(timezone.utc).date()
    week_anchor = _calendar_week_start(anchor_day)

    live_cal = await _google_calendar_snapshot(c, week_anchor)
    if live_cal is not None:
        data = {**dict(c["calendar"]), **live_cal}
    else:
        data = dict(c["calendar"])
        data["live"] = bool(c.get("google_tokens"))
        today = datetime.now(timezone.utc).date()
        seed_events = _normalize_seed_events(data.get("meetings") or [], today)
        data["events"] = seed_events
        data["week_start"] = week_anchor.strftime("%Y-%m-%d")
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
    week_end = (week_anchor + timedelta(days=6)).strftime("%Y-%m-%d")
    week_start_s = week_anchor.strftime("%Y-%m-%d")
    in_week_deadlines = [u for u in upcoming if week_start_s <= u["date"] <= week_end]
    events = list(data.get("events") or data.get("meetings") or [])
    if not data.get("events"):
        events = _normalize_seed_events(events, datetime.now(timezone.utc).date())
    existing_ids = {e.get("id") for e in events}
    for ev in _deadlines_as_events(in_week_deadlines):
        if ev["id"] not in existing_ids:
            events.append(ev)
    data["events"] = events
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data["meetings"] = [e for e in events if e.get("date") == today_str and not e.get("all_day")]
    if "focus_hours" not in data:
        data["focus_hours"], data["meeting_hours"] = gcal._compute_hours(data["meetings"])
    data["week_start"] = week_start_s
    helm_events = c.get("calendar", {}).get("helm_events") or []
    if helm_events:
        week_end_dt = week_anchor + timedelta(days=6)
        for ev in helm_events:
            ev_date = (ev.get("date") or (ev.get("start_at") or "")[:10]).strip()
            try:
                ev_day = datetime.strptime(ev_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            if week_anchor.date() <= ev_day <= week_end_dt.date():
                if ev.get("id") not in existing_ids:
                    events.append(ev)
                    existing_ids.add(ev.get("id"))
        data["events"] = events
    data["can_write"] = True
    data["google_connected"] = bool(c.get("google_tokens"))
    data["google_available"] = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    return data


class CalendarEventInput(BaseModel):
    title: str
    date: str
    time: str = "09:00"
    duration: int = 30
    type: str = "Internal"
    all_day: bool = False


def _build_helm_event(payload: CalendarEventInput, event_id: Optional[str] = None) -> dict:
    try:
        day = datetime.strptime(payload.date.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    eid = event_id or f"helm_{uuid.uuid4().hex[:10]}"
    if payload.all_day:
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        return {
            "id": eid, "title": payload.title.strip(), "date": day.isoformat(),
            "time": "", "duration": 0, "attendees": 0, "type": payload.type or "Internal",
            "prep": None, "importance": "medium", "source": "helm",
            "start_at": start.isoformat(), "end_at": end.isoformat(), "all_day": True,
        }
    parts = (payload.time or "09:00").split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
    duration = max(int(payload.duration or 30), 15)
    end = start + timedelta(minutes=duration)
    return {
        "id": eid, "title": payload.title.strip(), "date": day.isoformat(),
        "time": f"{hour:02d}:{minute:02d}", "duration": duration, "attendees": 0,
        "type": payload.type or "Internal", "prep": None, "importance": "medium", "source": "helm",
        "start_at": start.isoformat(), "end_at": end.isoformat(), "all_day": False,
    }


@api_router.post("/calendar/events")
async def create_calendar_event(payload: CalendarEventInput, principal=Depends(get_principal)):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    cal = dict(c.get("calendar") or {})
    events = list(cal.get("helm_events") or [])
    ev = _build_helm_event(payload)
    events.append(ev)
    cal["helm_events"] = events
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"calendar": cal}})
    await log_activity(principal, "calendar", "event.create", f"Added calendar event: {ev['title']}")
    return {"ok": True, "event": ev}


@api_router.patch("/calendar/events/{event_id}")
async def edit_calendar_event(event_id: str, payload: CalendarEventInput, principal=Depends(get_principal)):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    cal = dict(c.get("calendar") or {})
    events = list(cal.get("helm_events") or [])
    found = None
    for i, ev in enumerate(events):
        if ev.get("id") == event_id and ev.get("source") == "helm":
            events[i] = _build_helm_event(payload, event_id=event_id)
            found = events[i]
            break
    if not found:
        raise HTTPException(status_code=404, detail="Event not found")
    cal["helm_events"] = events
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"calendar": cal}})
    return {"ok": True, "event": found}


@api_router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str, principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    cal = dict(c.get("calendar") or {})
    events = [e for e in (cal.get("helm_events") or []) if e.get("id") != event_id]
    if len(events) == len(cal.get("helm_events") or []):
        raise HTTPException(status_code=404, detail="Event not found")
    cal["helm_events"] = events
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"calendar": cal}})
    return {"ok": True}


@api_router.get("/people")
async def people(principal=Depends(get_principal)):
    c = await sync_members_into_people(principal["workspace_id"])
    data = dict(c["people"])
    mem_ids = {
        m["membership_id"]
        for m in await db.memberships.find(
            {"workspace_id": principal["workspace_id"], "status": {"$in": ["active", "invited"]}},
            {"_id": 0, "membership_id": 1},
        ).to_list(200)
    }
    for p in data.get("people") or []:
        mid = p.get("membership_id")
        p["has_access"] = bool(mid and mid in mem_ids)
    data["can_write"] = await can_section_write(principal, "people", "people:write")
    data["can_invite_to_access"] = "members:invite" in perms_for(principal["pack"])
    data["departments"] = sec_access.DEFAULT_DEPARTMENTS
    return data


class PersonInput(BaseModel):
    name: str
    role: str = ""
    department: str = ""
    trust_score: int = 80
    quality: str = "B+"
    tasks_done: int = 0
    tenure: str = ""
    invite_to_access: bool = False
    email: Optional[EmailStr] = None
    pack: str = "member"


def _person_fields(payload: PersonInput):
    return {"name": payload.name.strip(), "role": payload.role.strip(),
            "department": payload.department.strip() or "General",
            "trust_score": payload.trust_score, "quality": payload.quality,
            "tasks_done": payload.tasks_done, "tenure": payload.tenure.strip() or "New"}


@api_router.post("/people")
async def add_person(payload: PersonInput, request: Request, principal=Depends(require_section("people", "people:write"))):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    invite = bool(payload.invite_to_access)
    email = _normalize_email(str(payload.email)) if payload.email else ""
    if invite:
        if "members:invite" not in perms_for(principal["pack"]):
            raise HTTPException(status_code=403, detail="You do not have permission to invite to Team & Access")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required to include in Team & Access")
        if payload.pack not in VALID_PACKS:
            raise HTTPException(status_code=400, detail="Unknown access pack")
        if payload.pack == "owner" and "members:manage" not in perms_for(principal["pack"]):
            raise HTTPException(status_code=403, detail="Only an owner can grant owner access")
        existing = await db.memberships.find_one({"workspace_id": principal["workspace_id"], "email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Already a member or invited — they should already be on the roster")
        await _enforce_seat_available(principal["workspace_id"])

    c = await get_ws(principal["workspace_id"])
    people = c["people"]
    person = {"id": f"p_{uuid.uuid4().hex[:8]}", **_person_fields(payload)}
    if email:
        person["email"] = email

    invite_meta = None
    if invite:
        pack = payload.pack
        role = "owner" if pack == "owner" else "member"
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        membership = {
            "membership_id": f"mem_{uuid.uuid4().hex[:12]}", "workspace_id": principal["workspace_id"],
            "user_id": existing_user["user_id"] if existing_user else None, "email": email,
            "role": role, "pack": pack, "department": person["department"],
            "status": "active" if existing_user else "invited",
            "invite_token": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.memberships.insert_one(membership)
        person["membership_id"] = membership["membership_id"]
        person["user_id"] = membership.get("user_id")
        person["has_access"] = True
        ws = c
        app_url = APP_URL or FRONTEND_URL or str(request.base_url).rstrip("/")
        email_result = await send_invite_email(
            email, principal.get("name") or "Your team lead", ws["name"],
            PACK_LABEL.get(pack, "Member"), app_url,
        )
        invite_meta = {"auto_joined": bool(existing_user), "email_sent": email_result.get("sent", False)}

    people["people"].append(person)
    people["avg_trust"] = _avg_trust(people["people"])
    headcount = len(people["people"])
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]},
                                   {"$set": {"people": people, "employees": headcount}})
    summary = f"Added {person['name']}" + (f" · {person['role']}" if person['role'] else "") + f" — headcount now {headcount}"
    if invite:
        summary += " · invited to Team & Access"
    await log_activity(principal, "people", "person.add", summary, {"headcount": headcount})
    out = {"ok": True, "person": person}
    if invite_meta:
        out.update(invite_meta)
    return out


@api_router.patch("/people/{person_id}")
async def edit_person(person_id: str, payload: PersonInput, principal=Depends(require_section("people", "people:write"))):
    c = await get_ws(principal["workspace_id"])
    people = c["people"]
    found = None
    for p in people["people"]:
        if p["id"] == person_id:
            fields = _person_fields(payload)
            p.update(fields)
            if payload.email:
                p["email"] = _normalize_email(str(payload.email))
            found = p
            break
    if not found:
        raise HTTPException(status_code=404, detail="Person not found")
    # Keep linked membership department in sync
    if found.get("membership_id"):
        await db.memberships.update_one(
            {"membership_id": found["membership_id"], "workspace_id": principal["workspace_id"]},
            {"$set": {"department": found["department"]}},
        )
    people["avg_trust"] = _avg_trust(people["people"])
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"people": people}})
    await log_activity(principal, "people", "person.edit", f"Updated {found['name']}'s profile")
    return {"ok": True}


@api_router.delete("/people/{person_id}")
async def remove_person(person_id: str, principal=Depends(require_section("people", "people:write"))):
    c = await get_ws(principal["workspace_id"])
    people = c["people"]
    person = next((p for p in people["people"] if p["id"] == person_id), None)
    if person and person.get("membership_id"):
        still = await db.memberships.find_one(
            {"membership_id": person["membership_id"], "workspace_id": principal["workspace_id"]},
            {"_id": 0, "membership_id": 1},
        )
        if still:
            raise HTTPException(
                status_code=400,
                detail="This person has Team & Access login — remove them from Team & Access first",
            )
    people["people"] = [p for p in people["people"] if p["id"] != person_id]
    people["avg_trust"] = _avg_trust(people["people"])
    headcount = len(people["people"])
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]},
                                   {"$set": {"people": people, "employees": headcount}})
    if person:
        await log_activity(principal, "people", "person.delete",
                           f"Removed {person['name']} — headcount now {headcount}", {"headcount": headcount})
    return {"ok": True}


# ------------------------- Department framework -------------------------
class EnableDepartmentInput(BaseModel):
    type: str


class DepartmentMemberInput(BaseModel):
    user_id: str
    role: str = "member"


async def _department_in_workspace(department_id: str, workspace_id: str) -> dict:
    doc = await db.departments.find_one(
        {"department_id": department_id, "workspace_id": workspace_id},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Department not found")
    return doc


@api_router.get("/departments")
async def list_departments(principal=Depends(get_principal)):
    """Catalog of all 7 types with enabled + current-user membership annotations."""
    ws_id = principal["workspace_id"]
    enabled_rows = await db.departments.find(
        {"workspace_id": ws_id, "enabled": True},
        {"_id": 0},
    ).to_list(50)
    by_type = {d["type"]: d for d in enabled_rows}
    my_rows = await db.department_members.find(
        {"user_id": principal["user_id"]},
        {"_id": 0},
    ).to_list(100)
    my_by_dept = {m["department_id"]: m for m in my_rows}
    is_ceo = dept_access.is_workspace_ceo(principal)

    out = []
    for entry in dept_catalog.DEPARTMENT_CATALOG:
        dtype = entry["type"]
        enabled_doc = by_type.get(dtype)
        membership = None
        if enabled_doc:
            membership = my_by_dept.get(enabled_doc["department_id"])
        out.append({
            "type": dtype,
            "name": entry["name"],
            "icon": entry["icon"],
            "enabled": bool(enabled_doc),
            "department_id": enabled_doc["department_id"] if enabled_doc else None,
            "is_member": bool(membership),
            "member_role": (membership or {}).get("role"),
            "visible_in_nav": bool(enabled_doc) and (is_ceo or bool(membership)),
        })
    return {
        "departments": out,
        "is_ceo": is_ceo,
        "can_manage": is_ceo,
    }


@api_router.post("/departments")
async def enable_department(payload: EnableDepartmentInput, principal=Depends(get_principal)):
    if not dept_access.is_workspace_ceo(principal):
        raise HTTPException(status_code=403, detail="Only the CEO can enable departments")
    dtype = (payload.type or "").strip().lower()
    if dtype not in dept_catalog.VALID_DEPARTMENT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown department type")
    existing = await db.departments.find_one(
        {"workspace_id": principal["workspace_id"], "type": dtype, "enabled": True},
        {"_id": 0},
    )
    if existing:
        raise HTTPException(status_code=409, detail="Department already enabled")
    now = datetime.now(timezone.utc).isoformat()
    department_id = f"dept_{uuid.uuid4().hex[:12]}"
    name = dept_catalog.default_name(dtype)
    await db.departments.insert_one({
        "department_id": department_id,
        "workspace_id": principal["workspace_id"],
        "type": dtype,
        "name": name,
        "enabled": True,
        "created_at": now,
    })
    return {
        "ok": True,
        "department": {
            "department_id": department_id,
            "type": dtype,
            "name": name,
            "enabled": True,
        },
    }


@api_router.delete("/departments/{department_id}")
async def disable_department(department_id: str, principal=Depends(get_principal)):
    if not dept_access.is_workspace_ceo(principal):
        raise HTTPException(status_code=403, detail="Only the CEO can disable departments")
    doc = await _department_in_workspace(department_id, principal["workspace_id"])
    if await dept_access.department_has_dependent_data(db, department_id):
        raise HTTPException(
            status_code=400,
            detail="Cannot disable this department while it still has department-specific data. Remove that data first.",
        )
    await db.department_members.delete_many({"department_id": department_id})
    await db.departments.delete_one(
        {"department_id": department_id, "workspace_id": principal["workspace_id"]},
    )
    return {"ok": True, "type": doc.get("type")}


@api_router.get("/departments/{department_id}/members")
async def list_department_members(department_id: str, principal=Depends(get_principal)):
    doc = await _department_in_workspace(department_id, principal["workspace_id"])
    if not doc.get("enabled"):
        raise HTTPException(status_code=404, detail="Department not found")
    if not await dept_access.can_access_department(db, principal, doc):
        raise HTTPException(status_code=403, detail="You do not have access to this department")
    rows = await db.department_members.find({"department_id": department_id}, {"_id": 0}).to_list(200)
    out = []
    for m in rows:
        u = await db.users.find_one({"user_id": m["user_id"]}, {"_id": 0, "name": 1, "email": 1, "picture": 1})
        out.append({
            "user_id": m["user_id"],
            "role": m.get("role") or "member",
            "created_at": m.get("created_at"),
            "name": (u or {}).get("name"),
            "email": (u or {}).get("email"),
            "picture": (u or {}).get("picture"),
        })
    out.sort(key=lambda x: ((x.get("name") or x.get("email") or "").lower(), x["user_id"]))
    return {
        "department_id": department_id,
        "type": doc["type"],
        "name": doc.get("name") or dept_catalog.default_name(doc["type"]),
        "members": out,
        "can_manage": await dept_access.can_manage_department_members(db, principal, department_id),
    }


@api_router.post("/departments/{department_id}/members")
async def add_department_member(
    department_id: str,
    payload: DepartmentMemberInput,
    principal=Depends(get_principal),
):
    doc = await _department_in_workspace(department_id, principal["workspace_id"])
    if not doc.get("enabled"):
        raise HTTPException(status_code=404, detail="Department not found")
    if not await dept_access.can_manage_department_members(db, principal, department_id):
        raise HTTPException(status_code=403, detail="Only the CEO or a department lead can add members")
    role = (payload.role or "member").strip().lower()
    if role not in dept_catalog.DEPARTMENT_MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Role must be member or lead")
    user_id = (payload.user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    ws_mem = await db.memberships.find_one(
        {"workspace_id": principal["workspace_id"], "user_id": user_id, "status": "active"},
        {"_id": 0},
    )
    if not ws_mem:
        raise HTTPException(status_code=400, detail="User is not an active member of this workspace")
    existing = await db.department_members.find_one(
        {"department_id": department_id, "user_id": user_id},
        {"_id": 0},
    )
    if existing:
        await db.department_members.update_one(
            {"department_id": department_id, "user_id": user_id},
            {"$set": {"role": role}},
        )
        return {"ok": True, "updated": True, "role": role}
    await db.department_members.insert_one({
        "department_id": department_id,
        "user_id": user_id,
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "updated": False, "role": role}


@api_router.delete("/departments/{department_id}/members/{user_id}")
async def remove_department_member(
    department_id: str,
    user_id: str,
    principal=Depends(get_principal),
):
    doc = await _department_in_workspace(department_id, principal["workspace_id"])
    if not doc.get("enabled"):
        raise HTTPException(status_code=404, detail="Department not found")
    if not await dept_access.can_manage_department_members(db, principal, department_id):
        raise HTTPException(status_code=403, detail="Only the CEO or a department lead can remove members")
    result = await db.department_members.delete_one(
        {"department_id": department_id, "user_id": user_id},
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Membership not found")
    return {"ok": True}


@api_router.get("/departments/by-type/{dept_type}")
async def get_department_by_type(dept_type: str, principal=Depends(get_principal)):
    """Resolve an enabled department by catalog type; enforce access for placeholder pages."""
    dtype = (dept_type or "").strip().lower()
    if dtype not in dept_catalog.VALID_DEPARTMENT_TYPES:
        raise HTTPException(status_code=404, detail="Unknown department type")
    doc = await db.departments.find_one(
        {"workspace_id": principal["workspace_id"], "type": dtype, "enabled": True},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Department is not enabled")
    if not await dept_access.can_access_department(db, principal, doc):
        raise HTTPException(status_code=403, detail="You do not have access to this department")
    membership = await dept_access.get_department_membership(db, doc["department_id"], principal["user_id"])
    return {
        "department_id": doc["department_id"],
        "type": doc["type"],
        "name": doc.get("name") or dept_catalog.default_name(doc["type"]),
        "icon": (dept_catalog.catalog_entry(doc["type"]) or {}).get("icon"),
        "is_ceo": dept_access.is_workspace_ceo(principal),
        "is_member": bool(membership),
        "member_role": (membership or {}).get("role"),
        "placeholder": dtype in dept_catalog.PLACEHOLDER_SHELL_TYPES,
        "can_manage_members": await dept_access.can_manage_department_members(
            db, principal, doc["department_id"],
        ),
    }


# ------------------------- Production chain -------------------------
PRODUCTION_STATUSES = frozenset({"not_started", "in_progress", "blocked", "done"})


async def _production_department(principal: dict) -> dict:
    """Enabled Production department for this workspace, with access enforced."""
    doc = await db.departments.find_one(
        {
            "workspace_id": principal["workspace_id"],
            "type": dept_catalog.TYPE_PRODUCTION,
            "enabled": True,
        },
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Production department is not enabled")
    if not await dept_access.can_access_department(db, principal, doc):
        raise HTTPException(status_code=403, detail="You do not have access to Production")
    return doc


def _can_lead_production(principal: dict, department_id: str, membership: dict | None) -> bool:
    if dept_access.is_workspace_ceo(principal):
        return True
    return bool(membership) and membership.get("role") == "lead"


async def _enrich_stage_assignees(stage: dict) -> dict:
    ids = list(stage.get("assigned_user_ids") or [])
    assignees = []
    for uid in ids:
        u = await db.users.find_one({"user_id": uid}, {"_id": 0, "name": 1, "email": 1, "picture": 1})
        assignees.append({
            "user_id": uid,
            "name": (u or {}).get("name"),
            "email": (u or {}).get("email"),
            "picture": (u or {}).get("picture"),
        })
    out = dict(stage)
    out["assignees"] = assignees
    return out


class ProductionStageCreate(BaseModel):
    name: str
    status: str = "not_started"
    assigned_user_ids: list[str] = []
    notes: str = ""


class ProductionStagePatch(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    assigned_user_ids: Optional[list[str]] = None
    notes: Optional[str] = None


class ProductionReorderInput(BaseModel):
    stage_ids: list[str]


@api_router.get("/production/stages")
async def list_production_stages(principal=Depends(get_principal)):
    dept = await _production_department(principal)
    rows = await db.production_stages.find(
        {"department_id": dept["department_id"]},
        {"_id": 0},
    ).sort("order", 1).to_list(500)
    stages = [await _enrich_stage_assignees(r) for r in rows]
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_production(principal, dept["department_id"], membership)
    return {
        "department_id": dept["department_id"],
        "name": dept.get("name") or "Production",
        "stages": stages,
        "is_ceo": dept_access.is_workspace_ceo(principal),
        "is_lead": is_lead,
        "can_edit_structure": is_lead,
        "can_update_stage": True,  # caller already passed access check
        "statuses": sorted(PRODUCTION_STATUSES),
    }


@api_router.post("/production/stages")
async def create_production_stage(payload: ProductionStageCreate, principal=Depends(get_principal)):
    dept = await _production_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    if not _can_lead_production(principal, dept["department_id"], membership):
        raise HTTPException(status_code=403, detail="Only the CEO or a Production lead can add stages")
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Stage name is required")
    status = (payload.status or "not_started").strip()
    if status not in PRODUCTION_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    assigned = [u for u in (payload.assigned_user_ids or []) if u]
    # Next order = max + 1
    last = await db.production_stages.find(
        {"department_id": dept["department_id"]},
        {"_id": 0, "order": 1},
    ).sort("order", -1).to_list(1)
    next_order = int((last[0]["order"] if last else -1)) + 1
    now = datetime.now(timezone.utc).isoformat()
    stage = {
        "id": f"pstage_{uuid.uuid4().hex[:10]}",
        "department_id": dept["department_id"],
        "workspace_id": principal["workspace_id"],
        "name": name,
        "order": next_order,
        "status": status,
        "assigned_user_ids": assigned,
        "notes": (payload.notes or "").strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.production_stages.insert_one(stage)
    return {"ok": True, "stage": await _enrich_stage_assignees({k: v for k, v in stage.items() if k != "_id"})}


@api_router.patch("/production/stages/reorder")
async def reorder_production_stages(payload: ProductionReorderInput, principal=Depends(get_principal)):
    dept = await _production_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    if not _can_lead_production(principal, dept["department_id"], membership):
        raise HTTPException(status_code=403, detail="Only the CEO or a Production lead can reorder stages")
    ids = [s for s in (payload.stage_ids or []) if s]
    if not ids:
        raise HTTPException(status_code=400, detail="stage_ids is required")
    existing = await db.production_stages.find(
        {"department_id": dept["department_id"]},
        {"_id": 0, "id": 1},
    ).to_list(500)
    existing_ids = {r["id"] for r in existing}
    if set(ids) != existing_ids:
        raise HTTPException(status_code=400, detail="stage_ids must include every stage exactly once")
    now = datetime.now(timezone.utc).isoformat()
    for i, sid in enumerate(ids):
        await db.production_stages.update_one(
            {"id": sid, "department_id": dept["department_id"]},
            {"$set": {"order": i, "updated_at": now}},
        )
    return {"ok": True}


@api_router.patch("/production/stages/{stage_id}")
async def patch_production_stage(
    stage_id: str,
    payload: ProductionStagePatch,
    principal=Depends(get_principal),
):
    dept = await _production_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_production(principal, dept["department_id"], membership)
    stage = await db.production_stages.find_one(
        {"id": stage_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    upd = {}
    if payload.name is not None:
        if not is_lead:
            raise HTTPException(status_code=403, detail="Only the CEO or a Production lead can rename stages")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Stage name is required")
        upd["name"] = name
    if payload.status is not None:
        status = payload.status.strip()
        if status not in PRODUCTION_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        upd["status"] = status
    if payload.assigned_user_ids is not None:
        upd["assigned_user_ids"] = [u for u in payload.assigned_user_ids if u]
    if payload.notes is not None:
        upd["notes"] = payload.notes.strip()
    if not upd:
        return {"ok": True, "stage": await _enrich_stage_assignees(stage)}
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.production_stages.update_one(
        {"id": stage_id, "department_id": dept["department_id"]},
        {"$set": upd},
    )
    updated = {**stage, **upd}
    return {"ok": True, "stage": await _enrich_stage_assignees(updated)}


@api_router.delete("/production/stages/{stage_id}")
async def delete_production_stage(stage_id: str, principal=Depends(get_principal)):
    dept = await _production_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    if not _can_lead_production(principal, dept["department_id"], membership):
        raise HTTPException(status_code=403, detail="Only the CEO or a Production lead can delete stages")
    result = await db.production_stages.delete_one(
        {"id": stage_id, "department_id": dept["department_id"]},
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Stage not found")
    # Compact order values
    rows = await db.production_stages.find(
        {"department_id": dept["department_id"]},
        {"_id": 0, "id": 1},
    ).sort("order", 1).to_list(500)
    now = datetime.now(timezone.utc).isoformat()
    for i, row in enumerate(rows):
        await db.production_stages.update_one(
            {"id": row["id"]},
            {"$set": {"order": i, "updated_at": now}},
        )
    return {"ok": True}


# ------------------------- Procurement request queue -------------------------
PROCUREMENT_STATUSES = frozenset({
    "requested", "approved", "ordered", "delivered", "rejected",
})
PROCUREMENT_CLOSED_STATUSES = frozenset({"delivered", "rejected"})
PROCUREMENT_APPROVAL_STATUSES = frozenset({"approved", "rejected"})


async def _procurement_department(principal: dict) -> dict:
    """Enabled Procurement department for this workspace, with access enforced."""
    doc = await db.departments.find_one(
        {
            "workspace_id": principal["workspace_id"],
            "type": dept_catalog.TYPE_PROCUREMENT,
            "enabled": True,
        },
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Procurement department is not enabled")
    if not await dept_access.can_access_department(db, principal, doc):
        raise HTTPException(status_code=403, detail="You do not have access to Procurement")
    return doc


def _can_lead_procurement(principal: dict, membership: dict | None) -> bool:
    if dept_access.is_workspace_ceo(principal):
        return True
    return bool(membership) and membership.get("role") == "lead"


async def _enrich_procurement_request(req: dict) -> dict:
    out = {k: v for k, v in req.items() if k != "_id"}
    for field, label in (("requested_by", "requester"), ("approved_by", "approver")):
        uid = out.get(field)
        info = None
        if uid:
            u = await db.users.find_one(
                {"user_id": uid}, {"_id": 0, "name": 1, "email": 1, "picture": 1},
            )
            info = {
                "user_id": uid,
                "name": (u or {}).get("name"),
                "email": (u or {}).get("email"),
                "picture": (u or {}).get("picture"),
            }
        out[label] = info
    return out


class ProcurementRequestCreate(BaseModel):
    item: str
    quantity: float = 1
    vendor_name: str = ""
    cost: Optional[float] = None
    notes: str = ""


class ProcurementRequestPatch(BaseModel):
    item: Optional[str] = None
    quantity: Optional[float] = None
    vendor_name: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None


@api_router.get("/procurement/requests")
async def list_procurement_requests(
    principal=Depends(get_principal),
    status: Optional[str] = Query(None),
):
    dept = await _procurement_department(principal)
    filt: dict = {"department_id": dept["department_id"]}
    if status is not None:
        st = status.strip().lower()
        if st not in PROCUREMENT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        filt["status"] = st
    rows = await db.procurement_requests.find(filt, {"_id": 0}).sort("created_at", -1).to_list(1000)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_procurement(principal, membership)
    items = [await _enrich_procurement_request(r) for r in rows]
    return {
        "department_id": dept["department_id"],
        "name": dept.get("name") or "Procurement",
        "requests": items,
        "statuses": ["requested", "approved", "ordered", "delivered", "rejected"],
        "is_ceo": dept_access.is_workspace_ceo(principal),
        "is_lead": is_lead,
        "can_approve": is_lead,
        "my_user_id": principal["user_id"],
    }


@api_router.post("/procurement/requests")
async def create_procurement_request(
    payload: ProcurementRequestCreate,
    principal=Depends(get_principal),
):
    dept = await _procurement_department(principal)
    item = (payload.item or "").strip()
    if not item:
        raise HTTPException(status_code=400, detail="Item is required")
    try:
        quantity = float(payload.quantity)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Quantity must be a number")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    cost = payload.cost
    if cost is not None:
        try:
            cost = round(float(cost), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Cost must be a number")
        if cost < 0:
            raise HTTPException(status_code=400, detail="Cost must be non-negative")
    now = datetime.now(timezone.utc).isoformat()
    req = {
        "id": f"preq_{uuid.uuid4().hex[:10]}",
        "department_id": dept["department_id"],
        "workspace_id": principal["workspace_id"],
        "item": item,
        "quantity": quantity,
        "vendor_name": (payload.vendor_name or "").strip(),
        "cost": cost,
        "requested_by": principal["user_id"],
        "approved_by": None,
        "status": "requested",
        "notes": (payload.notes or "").strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.procurement_requests.insert_one(dict(req))
    return {"ok": True, "request": await _enrich_procurement_request(req)}


@api_router.patch("/procurement/requests/{request_id}")
async def patch_procurement_request(
    request_id: str,
    payload: ProcurementRequestPatch,
    principal=Depends(get_principal),
):
    dept = await _procurement_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_procurement(principal, membership)
    req = await db.procurement_requests.find_one(
        {"id": request_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    is_owner = req.get("requested_by") == principal["user_id"]
    owner_can_edit_content = is_owner and req.get("status") == "requested"
    can_edit_content = is_lead or owner_can_edit_content

    upd: dict = {}
    content_touched = False

    if payload.item is not None:
        content_touched = True
        item = payload.item.strip()
        if not item:
            raise HTTPException(status_code=400, detail="Item is required")
        upd["item"] = item
    if payload.quantity is not None:
        content_touched = True
        try:
            quantity = float(payload.quantity)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Quantity must be a number")
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
        upd["quantity"] = quantity
    if payload.vendor_name is not None:
        content_touched = True
        upd["vendor_name"] = payload.vendor_name.strip()
    if payload.cost is not None:
        content_touched = True
        try:
            cost = round(float(payload.cost), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Cost must be a number")
        if cost < 0:
            raise HTTPException(status_code=400, detail="Cost must be non-negative")
        upd["cost"] = cost
    if payload.notes is not None:
        content_touched = True
        upd["notes"] = payload.notes.strip()

    if content_touched and not can_edit_content:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own requests while they are still requested",
        )

    if payload.status is not None:
        new_status = payload.status.strip().lower()
        if new_status not in PROCUREMENT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if new_status != req.get("status"):
            if new_status in PROCUREMENT_APPROVAL_STATUSES:
                if not is_lead:
                    raise HTTPException(
                        status_code=403,
                        detail="Only a Procurement lead or the CEO can approve or reject requests",
                    )
                upd["status"] = new_status
                if new_status == "approved":
                    upd["approved_by"] = principal["user_id"]
                # rejected leaves approved_by unchanged / None
            else:
                # ordered / delivered / back to requested — members may advance open work
                upd["status"] = new_status

    if not upd:
        return {"ok": True, "request": await _enrich_procurement_request(req)}

    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.procurement_requests.update_one(
        {"id": request_id, "department_id": dept["department_id"]},
        {"$set": upd},
    )
    return {"ok": True, "request": await _enrich_procurement_request({**req, **upd})}


@api_router.delete("/procurement/requests/{request_id}")
async def delete_procurement_request(request_id: str, principal=Depends(get_principal)):
    dept = await _procurement_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_procurement(principal, membership)
    req = await db.procurement_requests.find_one(
        {"id": request_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    is_owner = req.get("requested_by") == principal["user_id"]
    if is_lead:
        pass
    elif is_owner and req.get("status") == "requested":
        pass
    else:
        raise HTTPException(
            status_code=403,
            detail="Only the requester (while still requested) or a lead/CEO can delete this request",
        )
    await db.procurement_requests.delete_one(
        {"id": request_id, "department_id": dept["department_id"]},
    )
    return {"ok": True}


# ------------------------- Legal matter queue -------------------------
LEGAL_STATUSES = frozenset({
    "draft", "internal_review", "counterparty_review", "signed", "filed",
})
LEGAL_MEMBER_STATUSES = frozenset({"draft", "internal_review"})
LEGAL_LEAD_ONLY_STATUSES = frozenset({"counterparty_review", "signed", "filed"})
LEGAL_MATTER_TYPES = frozenset({"contract", "compliance", "other"})


async def _legal_department(principal: dict) -> dict:
    doc = await db.departments.find_one(
        {
            "workspace_id": principal["workspace_id"],
            "type": dept_catalog.TYPE_LEGAL,
            "enabled": True,
        },
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Legal department is not enabled")
    if not await dept_access.can_access_department(db, principal, doc):
        raise HTTPException(status_code=403, detail="You do not have access to Legal")
    return doc


def _can_lead_legal(principal: dict, membership: dict | None) -> bool:
    if dept_access.is_workspace_ceo(principal):
        return True
    return bool(membership) and membership.get("role") == "lead"


async def _enrich_legal_matter(matter: dict) -> dict:
    out = {k: v for k, v in matter.items() if k != "_id"}
    for field, label in (("assigned_to", "assignee"), ("created_by", "creator")):
        uid = out.get(field)
        info = None
        if uid:
            u = await db.users.find_one(
                {"user_id": uid}, {"_id": 0, "name": 1, "email": 1, "picture": 1},
            )
            info = {
                "user_id": uid,
                "name": (u or {}).get("name"),
                "email": (u or {}).get("email"),
                "picture": (u or {}).get("picture"),
            }
        out[label] = info
    doc_ref = out.get("document_ref")
    if isinstance(doc_ref, dict) and doc_ref.get("storage_key"):
        out["has_document"] = True
        out["document"] = {
            "filename": doc_ref.get("filename"),
            "content_type": doc_ref.get("content_type"),
            "uploaded_at": doc_ref.get("uploaded_at"),
            "document_id": doc_ref.get("document_id"),
        }
    else:
        out["has_document"] = False
        out["document"] = None
    return out


class LegalMatterCreate(BaseModel):
    title: str
    matter_type: str = "contract"
    assigned_to: Optional[str] = None
    notes: str = ""
    status: str = "draft"


class LegalMatterPatch(BaseModel):
    title: Optional[str] = None
    matter_type: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


def _normalize_matter_type(raw: str) -> str:
    t = (raw or "other").strip().lower() or "other"
    if t in LEGAL_MATTER_TYPES:
        return t
    # Keep loose free-text but cap length
    return (raw or "other").strip()[:80] or "other"


@api_router.get("/legal/matters")
async def list_legal_matters(
    principal=Depends(get_principal),
    status: Optional[str] = Query(None),
):
    dept = await _legal_department(principal)
    filt: dict = {"department_id": dept["department_id"]}
    if status is not None:
        st = status.strip().lower()
        if st not in LEGAL_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        filt["status"] = st
    rows = await db.legal_matters.find(filt, {"_id": 0}).sort("created_at", -1).to_list(1000)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_legal(principal, membership)
    items = [await _enrich_legal_matter(r) for r in rows]
    return {
        "department_id": dept["department_id"],
        "name": dept.get("name") or "Legal",
        "matters": items,
        "statuses": ["draft", "internal_review", "counterparty_review", "signed", "filed"],
        "matter_types": sorted(LEGAL_MATTER_TYPES),
        "is_ceo": dept_access.is_workspace_ceo(principal),
        "is_lead": is_lead,
        "can_reassign": is_lead,
        "can_advance_past_review": is_lead,
        "can_delete": is_lead,
        "my_user_id": principal["user_id"],
    }


@api_router.post("/legal/matters")
async def create_legal_matter(payload: LegalMatterCreate, principal=Depends(get_principal)):
    dept = await _legal_department(principal)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    status = (payload.status or "draft").strip().lower()
    if status not in LEGAL_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_legal(principal, membership)
    if status in LEGAL_LEAD_ONLY_STATUSES and not is_lead:
        raise HTTPException(
            status_code=403,
            detail="Only a Legal lead or the CEO can set this status",
        )
    assigned_to = (payload.assigned_to or "").strip() or principal["user_id"]
    now = datetime.now(timezone.utc).isoformat()
    matter = {
        "id": f"lmat_{uuid.uuid4().hex[:10]}",
        "department_id": dept["department_id"],
        "workspace_id": principal["workspace_id"],
        "title": title,
        "matter_type": _normalize_matter_type(payload.matter_type),
        "assigned_to": assigned_to,
        "created_by": principal["user_id"],
        "status": status if status in LEGAL_MEMBER_STATUSES or is_lead else "draft",
        "document_ref": None,
        "notes": (payload.notes or "").strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.legal_matters.insert_one(dict(matter))
    return {"ok": True, "matter": await _enrich_legal_matter(matter)}


@api_router.patch("/legal/matters/{matter_id}")
async def patch_legal_matter(
    matter_id: str,
    payload: LegalMatterPatch,
    principal=Depends(get_principal),
):
    dept = await _legal_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_legal(principal, membership)
    matter = await db.legal_matters.find_one(
        {"id": matter_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    is_assignee = matter.get("assigned_to") == principal["user_id"]
    can_update = is_lead or is_assignee
    if not can_update:
        raise HTTPException(status_code=403, detail="You can only update matters assigned to you")

    upd: dict = {}
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title is required")
        upd["title"] = title
    if payload.matter_type is not None:
        upd["matter_type"] = _normalize_matter_type(payload.matter_type)
    if payload.notes is not None:
        upd["notes"] = payload.notes.strip()

    if payload.assigned_to is not None:
        new_assignee = (payload.assigned_to or "").strip() or None
        if new_assignee != matter.get("assigned_to"):
            if not is_lead:
                raise HTTPException(
                    status_code=403,
                    detail="Only a Legal lead or the CEO can reassign a matter",
                )
            upd["assigned_to"] = new_assignee

    if payload.status is not None:
        new_status = payload.status.strip().lower()
        if new_status not in LEGAL_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if new_status != matter.get("status"):
            if new_status in LEGAL_LEAD_ONLY_STATUSES and not is_lead:
                raise HTTPException(
                    status_code=403,
                    detail="Only a Legal lead or the CEO can advance past internal review",
                )
            if not is_lead and new_status not in LEGAL_MEMBER_STATUSES:
                raise HTTPException(status_code=403, detail="Invalid status for your role")
            upd["status"] = new_status

    if not upd:
        return {"ok": True, "matter": await _enrich_legal_matter(matter)}

    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.legal_matters.update_one(
        {"id": matter_id, "department_id": dept["department_id"]},
        {"$set": upd},
    )
    return {"ok": True, "matter": await _enrich_legal_matter({**matter, **upd})}


@api_router.post("/legal/matters/{matter_id}/document")
async def upload_legal_matter_document(
    matter_id: str,
    file: UploadFile = File(...),
    principal=Depends(get_principal),
):
    """Attach or replace a document on a legal matter using R2 storage."""
    dept = await _legal_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_legal(principal, membership)
    matter = await db.legal_matters.find_one(
        {"id": matter_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    is_assignee = matter.get("assigned_to") == principal["user_id"]
    if not (is_lead or is_assignee):
        raise HTTPException(status_code=403, detail="You can only attach documents to matters assigned to you")

    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed. Upload PDF, PNG, or JPEG.")
    data = await file.read()
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 15MB.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if not doc_storage.r2_configured():
        raise HTTPException(status_code=503, detail="Document storage is not configured")

    filename = (file.filename or "document").replace("/", "_").replace("\\", "_")[:200]
    try:
        storage_key = await asyncio.to_thread(
            doc_storage.upload_document,
            principal["workspace_id"], data, filename, file.content_type,
        )
    except Exception as exc:
        logger.exception("legal matter document upload failed")
        raise HTTPException(status_code=500, detail="Could not store document") from exc

    # Best-effort cleanup of previous file
    old_ref = matter.get("document_ref") or {}
    old_key = old_ref.get("storage_key") if isinstance(old_ref, dict) else None
    if old_key and old_key != storage_key and doc_storage.r2_configured():
        try:
            await asyncio.to_thread(doc_storage.delete_document, old_key)
        except Exception:
            logger.exception("failed to delete previous legal matter document %s", old_key)

    now = datetime.now(timezone.utc).isoformat()
    doc_id = f"ldoc_{uuid.uuid4().hex[:12]}"
    document_ref = {
        "document_id": doc_id,
        "storage_key": storage_key,
        "filename": filename,
        "content_type": file.content_type,
        "uploaded_by": principal["user_id"],
        "uploaded_at": now,
    }
    await db.legal_matters.update_one(
        {"id": matter_id, "department_id": dept["department_id"]},
        {"$set": {"document_ref": document_ref, "updated_at": now}},
    )
    updated = {**matter, "document_ref": document_ref, "updated_at": now}
    return {"ok": True, "matter": await _enrich_legal_matter(updated)}


@api_router.get("/legal/matters/{matter_id}/document")
async def get_legal_matter_document(matter_id: str, principal=Depends(get_principal)):
    """Return metadata + presigned URL for the matter's current document."""
    dept = await _legal_department(principal)
    matter = await db.legal_matters.find_one(
        {"id": matter_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    doc_ref = matter.get("document_ref")
    if not isinstance(doc_ref, dict) or not doc_ref.get("storage_key"):
        raise HTTPException(status_code=404, detail="No document attached")
    if not doc_storage.r2_configured():
        raise HTTPException(status_code=503, detail="Document storage is not configured")
    try:
        presigned_url = await asyncio.to_thread(
            doc_storage.get_presigned_url, doc_ref["storage_key"],
        )
    except Exception as exc:
        logger.exception("presigned url failed for legal matter %s", matter_id)
        raise HTTPException(status_code=500, detail="Could not generate download URL") from exc
    return {
        "document_id": doc_ref.get("document_id"),
        "filename": doc_ref.get("filename"),
        "content_type": doc_ref.get("content_type"),
        "uploaded_at": doc_ref.get("uploaded_at"),
        "presigned_url": presigned_url,
    }


@api_router.delete("/legal/matters/{matter_id}")
async def delete_legal_matter(matter_id: str, principal=Depends(get_principal)):
    dept = await _legal_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    if not _can_lead_legal(principal, membership):
        raise HTTPException(status_code=403, detail="Only a Legal lead or the CEO can delete matters")
    matter = await db.legal_matters.find_one(
        {"id": matter_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    doc_ref = matter.get("document_ref") or {}
    storage_key = doc_ref.get("storage_key") if isinstance(doc_ref, dict) else None
    await db.legal_matters.delete_one(
        {"id": matter_id, "department_id": dept["department_id"]},
    )
    if storage_key and doc_storage.r2_configured():
        try:
            await asyncio.to_thread(doc_storage.delete_document, storage_key)
        except Exception:
            logger.exception("failed to delete legal matter document %s", storage_key)
    return {"ok": True}


# ------------------------- Engineering & Maintenance ticket queue -------------------------
MAINTENANCE_STATUSES = frozenset({"reported", "diagnosed", "in_repair", "resolved"})
MAINTENANCE_PRIORITIES = frozenset({"low", "medium", "high"})
_MAINT_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


async def _maintenance_department(principal: dict) -> dict:
    doc = await db.departments.find_one(
        {
            "workspace_id": principal["workspace_id"],
            "type": dept_catalog.TYPE_ENGINEERING_MAINTENANCE,
            "enabled": True,
        },
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Engineering & Maintenance department is not enabled",
        )
    if not await dept_access.can_access_department(db, principal, doc):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to Engineering & Maintenance",
        )
    return doc


def _can_lead_maintenance(principal: dict, membership: dict | None) -> bool:
    if dept_access.is_workspace_ceo(principal):
        return True
    return bool(membership) and membership.get("role") == "lead"


async def _enrich_maintenance_ticket(ticket: dict) -> dict:
    out = {k: v for k, v in ticket.items() if k != "_id"}
    for field, label in (("reported_by", "reporter"), ("assigned_technician", "technician")):
        uid = out.get(field)
        info = None
        if uid:
            u = await db.users.find_one(
                {"user_id": uid}, {"_id": 0, "name": 1, "email": 1, "picture": 1},
            )
            info = {
                "user_id": uid,
                "name": (u or {}).get("name"),
                "email": (u or {}).get("email"),
                "picture": (u or {}).get("picture"),
            }
        out[label] = info
    return out


def _sort_maintenance_tickets(rows: list) -> list:
    """Unresolved first, then high → medium → low priority, then newest."""
    def key(t):
        resolved = 1 if t.get("status") == "resolved" else 0
        pri = _MAINT_PRIORITY_RANK.get(t.get("priority") or "medium", 9)
        created = t.get("created_at") or ""
        return (resolved, pri, created)

    return sorted(rows, key=key)


class MaintenanceTicketCreate(BaseModel):
    equipment_name: str
    description: str = ""
    priority: str = "medium"
    notes: str = ""
    assigned_technician: Optional[str] = None


class MaintenanceTicketPatch(BaseModel):
    equipment_name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    assigned_technician: Optional[str] = None


@api_router.get("/maintenance/tickets")
async def list_maintenance_tickets(
    principal=Depends(get_principal),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
):
    dept = await _maintenance_department(principal)
    filt: dict = {"department_id": dept["department_id"]}
    if status is not None:
        st = status.strip().lower()
        if st not in MAINTENANCE_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        filt["status"] = st
    if priority is not None:
        pr = priority.strip().lower()
        if pr not in MAINTENANCE_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority filter")
        filt["priority"] = pr
    rows = await db.maintenance_tickets.find(filt, {"_id": 0}).to_list(1000)
    rows = _sort_maintenance_tickets(rows)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_maintenance(principal, membership)
    items = [await _enrich_maintenance_ticket(r) for r in rows]
    return {
        "department_id": dept["department_id"],
        "name": dept.get("name") or "Engineering & Maintenance",
        "tickets": items,
        "statuses": ["reported", "diagnosed", "in_repair", "resolved"],
        "priorities": ["low", "medium", "high"],
        "is_ceo": dept_access.is_workspace_ceo(principal),
        "is_lead": is_lead,
        "can_assign": is_lead,
        "can_delete": is_lead,
        "my_user_id": principal["user_id"],
    }


@api_router.post("/maintenance/tickets")
async def create_maintenance_ticket(
    payload: MaintenanceTicketCreate,
    principal=Depends(get_principal),
):
    dept = await _maintenance_department(principal)
    equipment = (payload.equipment_name or "").strip()
    if not equipment:
        raise HTTPException(status_code=400, detail="Equipment name is required")
    priority = (payload.priority or "medium").strip().lower()
    if priority not in MAINTENANCE_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority")
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_maintenance(principal, membership)
    assigned = None
    if is_lead and payload.assigned_technician is not None:
        assigned = (payload.assigned_technician or "").strip() or None
    now = datetime.now(timezone.utc).isoformat()
    ticket = {
        "id": f"mtkt_{uuid.uuid4().hex[:10]}",
        "department_id": dept["department_id"],
        "workspace_id": principal["workspace_id"],
        "equipment_name": equipment,
        "description": (payload.description or "").strip(),
        "reported_by": principal["user_id"],
        "assigned_technician": assigned,
        "priority": priority,
        "status": "reported",
        "notes": (payload.notes or "").strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.maintenance_tickets.insert_one(dict(ticket))
    return {"ok": True, "ticket": await _enrich_maintenance_ticket(ticket)}


@api_router.patch("/maintenance/tickets/{ticket_id}")
async def patch_maintenance_ticket(
    ticket_id: str,
    payload: MaintenanceTicketPatch,
    principal=Depends(get_principal),
):
    dept = await _maintenance_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    is_lead = _can_lead_maintenance(principal, membership)
    ticket = await db.maintenance_tickets.find_one(
        {"id": ticket_id, "department_id": dept["department_id"]},
        {"_id": 0},
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    is_tech = ticket.get("assigned_technician") == principal["user_id"]
    can_update = is_lead or is_tech
    if not can_update:
        raise HTTPException(
            status_code=403,
            detail="You can only update tickets assigned to you",
        )

    upd: dict = {}
    if payload.equipment_name is not None:
        name = payload.equipment_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Equipment name is required")
        upd["equipment_name"] = name
    if payload.description is not None:
        upd["description"] = payload.description.strip()
    if payload.notes is not None:
        upd["notes"] = payload.notes.strip()
    if payload.priority is not None:
        pr = payload.priority.strip().lower()
        if pr not in MAINTENANCE_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority")
        upd["priority"] = pr
    if payload.status is not None:
        st = payload.status.strip().lower()
        if st not in MAINTENANCE_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        upd["status"] = st

    if payload.assigned_technician is not None:
        new_tech = (payload.assigned_technician or "").strip() or None
        if new_tech != ticket.get("assigned_technician"):
            if not is_lead:
                raise HTTPException(
                    status_code=403,
                    detail="Only a lead or the CEO can assign a technician",
                )
            upd["assigned_technician"] = new_tech

    if not upd:
        return {"ok": True, "ticket": await _enrich_maintenance_ticket(ticket)}

    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.maintenance_tickets.update_one(
        {"id": ticket_id, "department_id": dept["department_id"]},
        {"$set": upd},
    )
    return {"ok": True, "ticket": await _enrich_maintenance_ticket({**ticket, **upd})}


@api_router.delete("/maintenance/tickets/{ticket_id}")
async def delete_maintenance_ticket(ticket_id: str, principal=Depends(get_principal)):
    dept = await _maintenance_department(principal)
    membership = await dept_access.get_department_membership(
        db, dept["department_id"], principal["user_id"],
    )
    if not _can_lead_maintenance(principal, membership):
        raise HTTPException(
            status_code=403,
            detail="Only a lead or the CEO can delete tickets",
        )
    result = await db.maintenance_tickets.delete_one(
        {"id": ticket_id, "department_id": dept["department_id"]},
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ok": True}


# ------------------------- Ask Helm -------------------------
class AskInput(BaseModel):
    message: str


@api_router.get("/ask/history")
async def ask_history(principal=Depends(get_principal)):
    msgs = await db.chat_messages.find({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


@api_router.post("/ask")
async def ask_helm(payload: AskInput, principal=Depends(require_pro_perm("ask:use"))):
    c = await get_ws(principal["workspace_id"])
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
    # gmail.readonly omitted — re-add only when email-forward document intake ships
    # (bills forwarded to a workspace address, parsed like uploaded documents).
]


def _provider_config(provider: str):
    redirect = _oauth_callback_uri(provider)
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
    ints = integ_catalog.merge_integrations(
        c,
        google_configured=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        qb_configured=bool(QB_CLIENT_ID and QB_CLIENT_SECRET),
        anthropic_configured=helm_llm.anthropic_configured(),
        r2_configured=doc_storage.r2_configured(),
        resend_configured=bool(RESEND_API_KEY),
        paddle_ready=bool(PADDLE_CLIENT_TOKEN and helm_plans.any_paddle_price_configured()),
        clerk_configured=clerk_auth.clerk_configured(),
    )
    return {
        "integrations": ints,
        "is_pro": workspace_is_pro(c),
        "can_manage": "integrations:manage" in perms_for(principal["pack"]),
        "slack_webhook_configured": bool((c.get("slack_webhook_url") or "").strip()),
        "slack_webhook_url": (c.get("slack_webhook_url") or "") if "integrations:manage" in perms_for(principal["pack"]) else "",
        "platform": {
            "clerk": clerk_auth.clerk_configured(),
            "anthropic": helm_llm.anthropic_configured(),
            "r2": doc_storage.r2_configured(),
            "resend": bool(RESEND_API_KEY),
            "paddle_ready": bool(PADDLE_CLIENT_TOKEN and helm_plans.any_paddle_price_configured()),
            "google": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
            "quickbooks": bool(QB_CLIENT_ID and QB_CLIENT_SECRET),
        },
        "oauth_redirect_uris": {
            "google": _oauth_callback_uri("google"),
            "quickbooks": _oauth_callback_uri("quickbooks"),
        },
    }


class SlackWebhookInput(BaseModel):
    webhook_url: str = ""


@api_router.put("/integrations/slack-webhook")
async def update_slack_webhook(payload: SlackWebhookInput, principal=Depends(require_pro_perm("integrations:manage"))):
    url = (payload.webhook_url or "").strip()
    if url and not url.startswith("https://hooks.slack.com/"):
        raise HTTPException(status_code=400, detail="Webhook URL must start with https://hooks.slack.com/")
    await db.workspaces.update_one(
        {"workspace_id": principal["workspace_id"]},
        {"$set": {"slack_webhook_url": url}},
    )
    await log_activity(
        principal, "integrations", "slack.webhook",
        "Updated Slack alert webhook" if url else "Cleared Slack alert webhook",
    )
    return {"ok": True, "slack_webhook_configured": bool(url)}


@api_router.post("/integrations/{integration_id}/toggle")
async def toggle_integration(integration_id: str, principal=Depends(require_pro_perm("integrations:manage"))):
    spec = next((i for i in integ_catalog.INTEGRATION_CATALOG if i["id"] == integration_id), None)
    if not spec:
        raise HTTPException(status_code=404, detail="Unknown integration")
    if spec.get("kind") in ("oauth", "coming_soon"):
        raise HTTPException(
            status_code=400,
            detail="Use Connect or Disconnect for this integration.",
        )
    raise HTTPException(status_code=400, detail="Integration toggle is not supported")


@api_router.get("/integrations/{provider}/connect")
async def integration_connect(provider: str, request: Request, principal=Depends(require_pro_perm("integrations:manage"))):
    cfg = _provider_config(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not cfg["configured"]:
        missing = {
            "google": "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET",
            "quickbooks": "QUICKBOOKS_CLIENT_ID / QUICKBOOKS_CLIENT_SECRET",
        }.get(provider, "OAuth credentials")
        return {
            "configured": False,
            "message": f"Not configured yet — set {missing} on the API host, then reconnect.",
            "redirect_uri": cfg["redirect_uri"],
        }
    params = {"client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "response_type": "code",
              "scope": cfg["scope"], "state": _sign_state(provider, principal["workspace_id"]), **cfg.get("extra", {})}
    return {"configured": True, "authorization_url": f"{cfg['auth_uri']}?{urlencode(params)}"}


@api_router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, realmId: Optional[str] = None):
    cfg = _provider_config(provider)
    frontend = (APP_URL or public_api_origin()).rstrip("/")
    integrations_path = f"{frontend}/app/integrations"
    if not cfg or not code or not state:
        return RedirectResponse(f"{integrations_path}?error=oauth")
    verified = _verify_state(state)
    if not verified or verified[0] != provider:
        return RedirectResponse(f"{integrations_path}?error=state")
    workspace_id = verified[1]
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            if provider == "quickbooks":
                # Intuit requires HTTP Basic auth for token exchange
                tr = await hc.post(
                    cfg["token_uri"],
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": cfg["redirect_uri"],
                    },
                    auth=(cfg["client_id"], cfg["client_secret"]),
                    headers={"Accept": "application/json"},
                )
            else:
                tr = await hc.post(
                    cfg["token_uri"],
                    data={
                        "code": code,
                        "client_id": cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                        "redirect_uri": cfg["redirect_uri"],
                        "grant_type": "authorization_code",
                    },
                    headers={"Accept": "application/json"},
                )
        if tr.status_code >= 400:
            logger.error("oauth token exchange %s failed: %s", provider, tr.text[:500])
            return RedirectResponse(f"{integrations_path}?error=token")
        tokens = tr.json()
        if tokens.get("error"):
            logger.error("oauth token error %s: %s", provider, tokens)
            return RedirectResponse(f"{integrations_path}?error=token")
        if realmId:
            tokens["realmId"] = realmId
        tokens["obtained_at"] = datetime.now(timezone.utc).isoformat()
        await db.workspaces.update_one({"workspace_id": workspace_id}, {"$set": {cfg["token_field"]: tokens}})
    except Exception:
        logger.exception("oauth token exchange failed")
        return RedirectResponse(f"{integrations_path}?error=token")
    return RedirectResponse(f"{integrations_path}?connected={provider}")


@api_router.post("/integrations/{provider}/disconnect")
async def integration_disconnect(provider: str, principal=Depends(require_pro_perm("integrations:manage"))):
    field = "google_tokens" if provider == "google" else "quickbooks_tokens" if provider == "quickbooks" else None
    if not field:
        raise HTTPException(status_code=404, detail="Unknown provider")
    unset = {}
    if provider == "quickbooks":
        unset["qb_last_synced_at"] = ""
    update: dict = {"$set": {field: None}}
    if unset:
        update["$unset"] = unset
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, update)
    return {"ok": True}


# Manual QuickBooks sync — periodic auto-sync (APScheduler / Render cron) is a natural next step.
@api_router.post("/integrations/quickbooks/sync")
async def quickbooks_sync(principal=Depends(require_pro_perm("integrations:manage"))):
    ws_id = principal["workspace_id"]
    c = await get_ws(ws_id)
    tokens = c.get("quickbooks_tokens")
    if not tokens:
        raise HTTPException(status_code=400, detail="QuickBooks is not connected — connect it in Integrations first.")
    realm_id = tokens.get("realmId")
    if not realm_id:
        raise HTTPException(status_code=400, detail="QuickBooks company (realmId) is missing — reconnect QuickBooks.")

    try:
        tokens = await qb_sync.refresh_qb_token(tokens)
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": {"quickbooks_tokens": tokens}})

        since = c.get("qb_last_synced_at")
        txns = await qb_sync.fetch_qb_transactions(tokens, realm_id, since)
        synced_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        finance_dept_id = await dept_migrate.finance_department_id(db, ws_id)

        for txn in txns:
            txn.pop("_qb_raw_type", None)
            qb_txn_id = txn.pop("qb_txn_id")
            existing = await db.financial_entries.find_one(
                {"workspace_id": ws_id, "qb_txn_id": qb_txn_id}, {"_id": 0, "id": 1},
            )
            fields = {
                "type": txn["type"],
                "category": txn["category"],
                "amount": txn["amount"],
                "month": txn["month"],
                "note": txn.get("note", ""),
                "recurring": txn.get("recurring", False),
                "source": "quickbooks_sync",
            }
            if existing:
                await db.financial_entries.update_one(
                    {"workspace_id": ws_id, "qb_txn_id": qb_txn_id},
                    {"$set": fields},
                )
            else:
                entry = {
                    "id": f"fe_{uuid.uuid4().hex[:10]}",
                    "workspace_id": ws_id,
                    "department_id": finance_dept_id,
                    "qb_txn_id": qb_txn_id,
                    "created_by": principal["user_id"],
                    "created_at": now_iso,
                    **fields,
                }
                await db.financial_entries.insert_one(entry)
            synced_count += 1

        last_synced_at = now_iso
        await db.workspaces.update_one({"workspace_id": ws_id}, {"$set": {"qb_last_synced_at": last_synced_at}})
        await log_activity(
            principal, "integrations", "quickbooks.sync",
            f"Synced {synced_count} transaction{'s' if synced_count != 1 else ''} from QuickBooks",
            {"synced_count": synced_count},
        )
        return {"ok": True, "synced_count": synced_count, "last_synced_at": last_synced_at}

    except qb_sync.QuickBooksAuthError as exc:
        logger.warning("QuickBooks auth failed for %s: %s", ws_id, exc)
        await db.workspaces.update_one(
            {"workspace_id": ws_id},
            {"$set": {"quickbooks_tokens": None}, "$unset": {"qb_last_synced_at": ""}},
        )
        raise HTTPException(
            status_code=401,
            detail="QuickBooks connection expired — please reconnect in Integrations.",
        ) from exc
    except Exception as exc:
        logger.exception("QuickBooks sync failed for %s", ws_id)
        raise HTTPException(status_code=502, detail="QuickBooks sync failed — try again shortly.") from exc


@api_router.get("/integrations/google/calendar-events")
async def google_calendar_events(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    tokens = c.get("google_tokens")
    if not tokens:
        raise HTTPException(status_code=400, detail="Google not connected")
    try:
        meetings, _, _, refreshed = await gcal.fetch_today_calendar(
            tokens, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, max_results=20,
        )
        if refreshed is not tokens:
            await db.workspaces.update_one(
                {"workspace_id": c["workspace_id"]},
                {"$set": {"google_tokens": refreshed}},
            )
        return {"events": meetings, "live": True}
    except gcal.GoogleAuthError as exc:
        await db.workspaces.update_one(
            {"workspace_id": c["workspace_id"]},
            {"$set": {"google_tokens": None}},
        )
        raise HTTPException(status_code=401, detail=str(exc)) from exc


# ------------------------- Payments -------------------------
async def get_billing_status(workspace_id: str, pack: str):
    c = await get_ws(workspace_id)
    plan = workspace_plan_id(c)
    pdef = helm_plans.plan_def(plan)
    sub_status = c.get("subscription_status") or c.get("billing_status")
    has_customer = bool(c.get("paddle_customer_id"))
    period = plan_usage.current_usage_period(c)
    extracts_used = await plan_usage.get_period_extract_count(db, workspace_id, period["key"])
    extracts_limit = helm_plans.ai_extracts_limit(plan)
    seats_used = await _seat_count(workspace_id)
    seats_limit = helm_plans.seats_limit(plan)
    plans = helm_plans.public_plan_list()
    client_ready = bool(PADDLE_CLIENT_TOKEN)
    for row in plans:
        if row["id"] != helm_plans.PLAN_FREE:
            row["checkout_available"] = bool(row["checkout_available"] and client_ready)
    pending = c.get("pending_plan")
    return {
        "current_plan": plan,
        "legacy_plan": c.get("plan"),
        "plan_label": pdef["label"],
        "is_paid": helm_plans.is_paid_plan(plan),
        "pro_only": False,
        "billing_enforced": BILLING_ENFORCED,
        "requires_activation": False,
        "trial_days": TRIAL_DAYS,
        "pro_price": pdef["price"] if helm_plans.is_paid_plan(plan) else helm_plans.PLANS[helm_plans.PLAN_STARTER]["price"],
        "price": pdef["price"],
        "plans": plans,
        "features": dict(pdef["features"]),
        "seats_used": seats_used,
        "seats_limit": seats_limit,
        "ai_extracts_used": extracts_used,
        "ai_extracts_limit": extracts_limit,
        "usage_period_key": period["key"],
        "usage_period_start": period["start"].isoformat(),
        "usage_period_end": period["end"].isoformat(),
        "pending_plan": helm_plans.normalize_plan(pending) if pending else None,
        "pending_plan_effective_at": c.get("pending_plan_effective_at"),
        "can_manage": "billing:manage" in perms_for(pack),
        "paddle_ready": client_ready and helm_plans.any_paddle_price_configured(),
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


class SchedulePlanInput(BaseModel):
    plan: str


@api_router.post("/billing/schedule-plan")
async def schedule_plan_change(payload: SchedulePlanInput, principal=Depends(require("billing:manage"))):
    """Schedule a downgrade for the end of the current billing period (no mid-cycle refunds)."""
    c = await get_ws(principal["workspace_id"])
    current = workspace_plan_id(c)
    target = helm_plans.normalize_plan(payload.plan)
    if target == current:
        await db.workspaces.update_one(
            {"workspace_id": principal["workspace_id"]},
            {"$unset": {"pending_plan": "", "pending_plan_effective_at": ""}},
        )
        return {"ok": True, "current_plan": current, "pending_plan": None}
    if helm_plans.is_upgrade(current, target):
        raise HTTPException(
            status_code=400,
            detail="Upgrades require Paddle checkout — use the Upgrade button on Billing.",
        )
    period = plan_usage.current_usage_period(c)
    effective_at = period["end"].isoformat()
    await db.workspaces.update_one(
        {"workspace_id": principal["workspace_id"]},
        {"$set": {"pending_plan": target, "pending_plan_effective_at": effective_at}},
    )
    return {
        "ok": True,
        "current_plan": current,
        "pending_plan": target,
        "pending_plan_effective_at": effective_at,
        "message": f"Downgrade to {helm_plans.plan_def(target)['label']} takes effect at the end of the current billing period. No refund for the remaining period.",
    }


@api_router.post("/demo/reset-plan")
async def reset_plan(principal=Depends(require("billing:manage"))):
    if not DEMO_RESET_ENABLED:
        raise HTTPException(status_code=403, detail="Demo reset is disabled")
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {
        "$set": {"plan": "free", "subscription_status": None, "billing_status": None},
        "$unset": {
            "paddle_subscription_id": "", "paddle_customer_id": "",
            "pending_plan": "", "pending_plan_effective_at": "",
        },
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


class PaddleConfigInput(BaseModel):
    plan: str = helm_plans.PLAN_STARTER


@api_router.post("/billing/paddle/config")
async def paddle_config(request: Request, principal=Depends(require("billing:manage"))):
    if not PADDLE_CLIENT_TOKEN:
        raise HTTPException(status_code=400, detail="Paddle is not configured")
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    target = helm_plans.normalize_plan(raw.get("plan") or helm_plans.PLAN_STARTER)
    if target == helm_plans.PLAN_FREE:
        raise HTTPException(status_code=400, detail="Free plan does not require checkout")
    price_id = helm_plans.paddle_price_id_for(target)
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"Checkout for {helm_plans.plan_def(target)['label']} is not configured yet — set the Paddle price ID env var",
        )
    nonce = uuid.uuid4().hex
    await db.paddle_intents.insert_one({
        "_id": nonce,
        "workspace_id": principal["workspace_id"],
        "user_id": principal["user_id"],
        "price_id": price_id,
        "plan": target,
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    return {
        "client_token": PADDLE_CLIENT_TOKEN,
        "price_id": price_id,
        "plan": target,
        "trial_days": TRIAL_DAYS,
        "environment": PADDLE_ENV,
        "checkout_nonce": nonce,
        "workspace_id": principal["workspace_id"],
        "user_id": principal["user_id"],
        "email": principal.get("email"),
    }


async def _paddle_provision(event, status: str = "active"):
    data = event.get("data") or {}
    custom = data.get("custom_data") or {}
    nonce = custom.get("checkout_nonce")
    workspace_id = custom.get("workspace_id")
    user_id = custom.get("user_id")
    sub_id = data.get("subscription_id") or data.get("id")
    now_iso = event.get("occurred_at") or datetime.now(timezone.utc).isoformat()

    # Recovery path: subscription reactivated / updated without checkout nonce
    # (e.g. past_due → active). Bind by paddle_subscription_id.
    if not (nonce and workspace_id and user_id):
        if not sub_id or status not in ("active", "trialing"):
            return
        recovery = {
            "subscription_status": status,
            "billing_status": status,
            "paddle_last_event_at": now_iso,
        }
        if data.get("customer_id"):
            recovery["paddle_customer_id"] = data["customer_id"]
        await db.workspaces.update_one(
            {"paddle_subscription_id": sub_id},
            {"$set": recovery, "$unset": {"canceled_at": ""}},
        )
        return

    intent = await db.paddle_intents.find_one({"_id": nonce})
    if not intent or intent.get("workspace_id") != workspace_id or intent.get("user_id") != user_id:
        return
    plan = intent.get("plan") or helm_plans.plan_for_paddle_price(intent.get("price_id")) or helm_plans.PLAN_STARTER
    plan = helm_plans.normalize_plan(plan)
    if plan == helm_plans.PLAN_FREE:
        plan = helm_plans.PLAN_STARTER
    set_fields = {
        "plan": plan, "billing_provider": "paddle",
        "paddle_subscription_id": sub_id,
        "paddle_customer_id": data.get("customer_id"),
        "paddle_last_event_at": now_iso,
        "subscription_status": status, "billing_status": status,
        "subscription_started_at": now_iso,
    }
    # Anchor usage periods on first provision only
    existing = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "billing_period_start": 1})
    if not (existing or {}).get("billing_period_start"):
        set_fields["billing_period_start"] = now_iso
    await db.workspaces.update_one({"workspace_id": workspace_id}, {"$set": set_fields, "$unset": {
        "canceled_at": "", "pending_plan": "", "pending_plan_effective_at": "",
    }})
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
        await _paddle_provision(event, status="active")
    elif event_type in ("subscription.created", "subscription.activated", "subscription.updated", "subscription.trialing"):
        status = (event.get("data") or {}).get("status") or "active"
        if status in ("active", "trialing"):
            await _paddle_provision(event, status=status)
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
    "paddle_intents", "payment_transactions", "procurement_requests", "legal_matters",
    "maintenance_tickets",
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


async def _mongo_ping() -> bool:
    try:
        await asyncio.wait_for(db.command("ping", maxTimeMS=2000), timeout=3.0)
        return True
    except Exception:
        return False


async def _require_mongo() -> None:
    if await _mongo_ping():
        return
    await _connect_mongo_at_startup()
    if not await _mongo_ping():
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Check MONGO_URL and Atlas Network Access on Render.",
        )


async def _probe_mongo_candidates() -> list[dict]:
    results: list[dict] = []
    for url in _mongo_candidate_urls():
        probe = _make_mongo_client(url)
        ok = False
        err: str | None = None
        try:
            await asyncio.wait_for(probe.admin.command("ping", maxTimeMS=2000), timeout=3.0)
            ok = True
        except Exception as exc:
            err = type(exc).__name__
        finally:
            probe.close()
        results.append({
            "source": _mongo_source_label(url),
            "url": _redact_mongo_url(url),
            "ok": ok,
            "error": err,
        })
    return results


@api_router.get("/setup/status")
async def setup_status():
    """Production readiness probe — no secrets."""
    mongo_ok = await _mongo_ping()
    probes = await _probe_mongo_candidates()
    clerk_sync = clerk_auth.clerk_sync_status()
    oauth_redirects = {
        "google": _oauth_callback_uri("google"),
        "quickbooks": _oauth_callback_uri("quickbooks"),
    }
    return {
        "frontend_url": FRONTEND_URL or None,
        "app_url": APP_URL or None,
        "public_api_origin": public_api_origin(),
        "clerk_enabled": clerk_auth.clerk_configured(),
        "clerk_jwks_host": clerk_auth.CLERK_JWKS_URL.split("/")[2] if clerk_auth.CLERK_JWKS_URL else None,
        "clerk_secret_mode": (
            "live" if clerk_auth.CLERK_SECRET_KEY.startswith("sk_live_")
            else "test" if clerk_auth.CLERK_SECRET_KEY.startswith("sk_test_")
            else "unknown"
        ) if clerk_auth.clerk_configured() else None,
        "clerk_publishable_key_set": bool(CLERK_PUBLISHABLE_KEY),
        "clerk_keys_aligned": (
            clerk_auth.clerk_keys_aligned(CLERK_PUBLISHABLE_KEY, clerk_auth.CLERK_JWKS_URL)
            if CLERK_PUBLISHABLE_KEY
            else None
        ),
        "clerk_api_ok": await clerk_auth.clerk_api_ok() if clerk_auth.clerk_configured() else False,
        "clerk_google_oauth": await clerk_auth.clerk_google_oauth_status() if clerk_auth.clerk_configured() else None,
        "clerk_sync": clerk_sync,
        "clerk_instance_env": clerk_sync.get("environment_type"),
        "mongo": mongo_ok,
        "mongo_source": MONGO_SOURCE,
        "mongo_url": _redact_mongo_url(mongo_url),
        "mongo_candidates": len(_mongo_candidate_urls()),
        "mongo_probes": probes,
        "use_atlas_mongo": os.environ.get("USE_ATLAS_MONGO", "false"),
        "on_render": bool(os.environ.get("RENDER")),
        "git_commit": os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT"),
        "integrations": {
            "google_calendar": {
                "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
                "env": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
                "redirect_uri": oauth_redirects["google"],
            },
            "quickbooks": {
                "configured": bool(QB_CLIENT_ID and QB_CLIENT_SECRET),
                "env": ["QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET", "QUICKBOOKS_ENV"],
                "redirect_uri": oauth_redirects["quickbooks"],
                "env_value": QB_ENV,
            },
            "anthropic": {
                "configured": helm_llm.anthropic_configured(),
                "env": ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"],
            },
            "r2": {
                "configured": doc_storage.r2_configured(),
                "env": ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_ENDPOINT"],
            },
            "resend": {
                "configured": bool(RESEND_API_KEY),
                "env": ["RESEND_API_KEY", "SENDER_EMAIL"],
            },
            "paddle": {
                "configured": bool(PADDLE_CLIENT_TOKEN and PADDLE_PRICE_ID),
                "env": ["PADDLE_API_KEY", "PADDLE_CLIENT_TOKEN", "PADDLE_PRICE_ID", "PADDLE_WEBHOOK_SECRET", "PADDLE_ENV"],
            },
        },
        "oauth_redirect_uris": oauth_redirects,
    }


@api_router.get("/setup/google-oauth")
async def setup_google_oauth():
    """Clerk Google OAuth readiness — verifies redirect URI is registered in Google Cloud."""
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    return await clerk_auth.clerk_google_oauth_status()


@api_router.post("/setup/clerk-sync")
async def setup_clerk_sync(request: Request):
    """Force Clerk instance sync (allowed_origins + development_origin for Vercel)."""
    _require_setup_secret(request)
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    result = await clerk_auth.sync_clerk_instance()
    if not result.get("synced"):
        raise HTTPException(status_code=503, detail=result)
    return result


@api_router.post("/admin/cleanup-orphaned-documents")
async def cleanup_orphaned_documents_admin(request: Request):
    """Delete uncommitted document uploads older than DOC_ORPHAN_RETENTION_DAYS (default 7)."""
    _require_setup_secret(request)
    return await document_cleanup.cleanup_orphaned_documents(db)


@api_router.get("/health")
async def health():
    """Liveness probe for Render — must return 200 within 5s even when Mongo is down."""
    mongo_ok = await _mongo_ping()
    return {"status": "ok", "mongo": mongo_ok, "mongo_source": MONGO_SOURCE}


@api_router.get("/")
async def root():
    return {"service": "Helm CEO Operating System"}


_serve_static = should_serve_static()
if not _serve_static:

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

_cors_origins = list(dict.fromkeys(
    CORS_ORIGINS + clerk_auth.helm_frontend_origins()
)) or (clerk_auth.helm_frontend_origins() or ["http://localhost:3000"])
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

if _serve_static:
    mount_static_frontend(app)


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
        (db.deals, [("workspace_id", 1), ("department_id", 1)], {}),
        (db.financial_entries, [("workspace_id", 1)], {}),
        (db.financial_entries, [("workspace_id", 1), ("department_id", 1)], {}),
        (db.financial_entries, [("workspace_id", 1), ("qb_txn_id", 1)], {"unique": True, "sparse": True}),
        (db.documents, [("workspace_id", 1)], {}),
        (db.documents, [("id", 1)], {"unique": True}),
        (db.document_rate_events, [("created_at", 1)], {"expireAfterSeconds": 3600}),
        (db.document_rate_events, [("workspace_id", 1), ("action", 1)], {}),
        (db.insights_rate_events, [("created_at", 1)], {"expireAfterSeconds": 86400}),
        (db.insights_rate_events, [("workspace_id", 1)], {}),
        (db.activities, [("workspace_id", 1)], {}),
        (db.updates, [("workspace_id", 1)], {}),
        (db.chat_messages, [("workspace_id", 1)], {}),
        (db.departments, [("workspace_id", 1), ("type", 1)], {"unique": True}),
        (db.departments, [("department_id", 1)], {"unique": True}),
        (db.department_members, [("department_id", 1), ("user_id", 1)], {"unique": True}),
        (db.department_members, [("user_id", 1)], {}),
        (db.production_stages, [("id", 1)], {"unique": True}),
        (db.production_stages, [("department_id", 1), ("order", 1)], {}),
        (db.production_stages, [("workspace_id", 1)], {}),
        (db.procurement_requests, [("id", 1)], {"unique": True}),
        (db.procurement_requests, [("department_id", 1), ("created_at", -1)], {}),
        (db.procurement_requests, [("department_id", 1), ("status", 1)], {}),
        (db.procurement_requests, [("workspace_id", 1)], {}),
        (db.legal_matters, [("id", 1)], {"unique": True}),
        (db.legal_matters, [("department_id", 1), ("created_at", -1)], {}),
        (db.legal_matters, [("department_id", 1), ("status", 1)], {}),
        (db.legal_matters, [("workspace_id", 1)], {}),
        (db.maintenance_tickets, [("id", 1)], {"unique": True}),
        (db.maintenance_tickets, [("department_id", 1), ("status", 1)], {}),
        (db.maintenance_tickets, [("department_id", 1), ("priority", 1)], {}),
        (db.maintenance_tickets, [("workspace_id", 1)], {}),
    ]
    for collection, keys, opts in specs:
        try:
            await asyncio.wait_for(collection.create_index(keys, **opts), timeout=1.5)
        except Exception:
            logger.debug("index ensure skipped for %s", keys, exc_info=True)


async def _connect_mongo_at_startup() -> None:
    """Probe candidate URLs and bind to the first reachable Mongo (fixes stale Atlas env on Render)."""
    global client, db, mongo_url, MONGO_SOURCE
    candidates = _mongo_candidate_urls()
    if not candidates:
        logger.error("No Mongo URL configured — set MONGO_URL or sync render.yaml")
        return

    for attempt in range(1, 6):
        for url in candidates:
            probe = _make_mongo_client(url)
            try:
                await asyncio.wait_for(
                    probe.admin.command("ping", maxTimeMS=3000),
                    timeout=5.0,
                )
            except Exception as exc:
                probe.close()
                logger.warning(
                    "Mongo unreachable attempt %d (%s): %s",
                    attempt, _redact_mongo_url(url), exc,
                )
                continue
            if probe is not client:
                client.close()
            client = probe
            db = client[DB_NAME]
            mongo_url = url
            MONGO_SOURCE = _mongo_source_label(url)
            logger.info("Mongo connected via %s (%s)", MONGO_SOURCE, _redact_mongo_url(url))
            return
        if attempt < 5:
            await asyncio.sleep(min(2 * attempt, 8))

    logger.error("Mongo unavailable after probing %d candidate URL(s)", len(candidates))


@app.on_event("startup")
async def startup():
    await _connect_mongo_at_startup()
    # Do not block Render health checks — indexes / migrations run after listen.
    asyncio.create_task(_ensure_indexes())
    asyncio.create_task(_run_sales_finance_migration())
    asyncio.create_task(clerk_auth.sync_clerk_instance())
    if clerk_auth.clerk_configured():
        asyncio.create_task(clerk_auth.prefetch_jwks())


async def _run_sales_finance_migration() -> None:
    """Idempotent fold of Sales + Accounting/Finance into the department system."""
    try:
        await dept_migrate.migrate_all_workspaces_sales_finance(db)
    except Exception:
        logger.exception("sales/finance department migration failed")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
