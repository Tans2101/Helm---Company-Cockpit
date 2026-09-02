import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db import db
from deps import get_principal, get_ws, pack_of, perms_for, require_pro_perm, PACK_LABEL
from helpers import log_activity

router = APIRouter()

@router.get("/team")
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


@router.get("/calendar")
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


@router.get("/people")
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


@router.post("/people")
async def add_person(payload: PersonInput, principal=Depends(require_pro_perm("people:write"))):
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


@router.patch("/people/{person_id}")
async def edit_person(person_id: str, payload: PersonInput, principal=Depends(require_pro_perm("people:write"))):
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


@router.delete("/people/{person_id}")
async def remove_person(person_id: str, principal=Depends(require_pro_perm("people:write"))):
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
