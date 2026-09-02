import uuid
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from db import APP_URL, FRONTEND_URL, db
from deps import (
    _check_join_rate_limit,
    _client_ip,
    get_principal,
    get_user,
    get_ws,
    pack_of,
    perms_for,
    require,
    require_pro_perm,
    VALID_PACKS,
    PACK_LABEL,
)
from helpers import send_invite_email
from seed_data import build_workspace, sample_financial_entries, gen_join_code

router = APIRouter()

# ------------------------- Workspaces & members -------------------------
@router.get("/workspaces")
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


@router.post("/workspaces/switch")
async def switch_workspace(payload: SwitchInput, principal=Depends(get_principal)):
    m = await db.memberships.find_one({"user_id": principal["user_id"], "workspace_id": payload.workspace_id, "status": "active"}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await db.users.update_one({"user_id": principal["user_id"]}, {"$set": {"active_workspace_id": payload.workspace_id}})
    return {"ok": True, "workspace_id": payload.workspace_id}


class CreateWsInput(BaseModel):
    name: str


@router.post("/workspaces")
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


@router.get("/workspaces/join-info")
async def join_info(code: str, user=Depends(get_user)):
    c = code.strip()
    ws = await db.workspaces.find_one({"join_code": c}, {"_id": 0, "name": 1, "workspace_id": 1})
    if not ws:
        ws = await db.workspaces.find_one({"join_code": c.upper()}, {"_id": 0, "name": 1, "workspace_id": 1})
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return {"name": ws["name"], "workspace_id": ws["workspace_id"]}


@router.post("/workspaces/join")
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


@router.get("/workspaces/join-code")
async def get_join_code(principal=Depends(require_pro_perm("members:invite"))):
    ws = await get_ws(principal["workspace_id"])
    code = ws.get("join_code")
    if not code:
        code = gen_join_code()
        await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {"$set": {"join_code": code}})
    return {"join_code": code}


@router.get("/members")
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


@router.post("/members/invite")
async def invite_member(payload: InviteInput, request: Request, principal=Depends(require_pro_perm("members:invite"))):
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


@router.patch("/members/{membership_id}")
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
    await db.memberships.update_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"$set": {"role": role, "pack": pack}})
    return {"ok": True}


@router.delete("/members/{membership_id}")
async def remove_member(membership_id: str, principal=Depends(require_pro_perm("members:manage"))):
    m = await db.memberships.find_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.get("user_id") == principal["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    await db.memberships.delete_one({"membership_id": membership_id, "workspace_id": principal["workspace_id"]})
    return {"ok": True}


# ------------------------- Company / module data -------------------------
@router.get("/company")
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


@router.patch("/company")
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


@router.post("/workspace/apply-template")
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
