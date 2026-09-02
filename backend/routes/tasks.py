import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import llm as helm_llm
from db import db
from deps import get_principal, get_ws, perms_for, require_pro_perm, workspace_is_pro
from helpers import compute_financials, log_activity, rel_time

router = APIRouter()

@router.get("/tasks")
async def tasks(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    t = dict(c["tasks"])
    t["can_create"] = "tasks:create" in perms_for(principal["pack"])
    t["can_assign"] = "tasks:assign" in perms_for(principal["pack"])
    t["my_user_id"] = principal["user_id"]
    return t


@router.get("/tasks/me")
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


@router.post("/tasks")
async def create_task(payload: TaskInput, principal=Depends(require_pro_perm("tasks:create"))):
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


@router.patch("/tasks/{task_id}")
async def move_task(task_id: str, payload: TaskMove, principal=Depends(require_pro_perm("tasks:move"))):
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


@router.get("/updates/me")
async def my_update(principal=Depends(get_principal)):
    day = datetime.now(timezone.utc).date().isoformat()
    u = await db.updates.find_one({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"], "day": day}, {"_id": 0})
    return {"update": u, "day": day}


@router.get("/updates/today")
async def todays_updates(principal=Depends(get_principal)):
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": principal["workspace_id"], "day": day}, {"_id": 0}).sort("updated_at", -1).to_list(50)
    for u in ups:
        u["ago"] = rel_time(u.get("updated_at", ""))
    return {"updates": ups, "day": day}


@router.post("/updates")
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


@router.get("/reports")
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
    return {"reports": reports, "is_pro": workspace_is_pro(c)}


@router.post("/reports/weekly-pack")
async def weekly_pack(principal=Depends(require_pro_perm("reports:pack"))):
    c = await get_ws(principal["workspace_id"])
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI is not configured (ANTHROPIC_API_KEY)")
    context = {"company": c["name"], "financials": await compute_financials(c["workspace_id"]),
               "kpis": c["telemetry"]["kpis"], "reports": [{"title": r["title"], "summary": r["summary"]} for r in c["reports"]]}
    system = ("You are Helm, writing the Weekly CEO Pack. Produce a board-ready weekly summary in markdown with sections: "
              "Headline, Growth, Financial Health, Risks, and This Week's Focus. Be concise, executive, and specific.")
    text = await helm_llm.complete(system, f"Data:\n{json.dumps(context, indent=2)}\n\nWrite the Weekly CEO Pack.")
    return {"content": text}
