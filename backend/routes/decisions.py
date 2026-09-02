import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import llm as helm_llm
from db import db
from deps import (
    get_principal,
    get_ws,
    perms_for,
    require_pro_perm,
    workspace_is_pro,
)
from helpers import compute_financials, log_activity, rel_time

router = APIRouter()

@router.get("/briefing")
async def briefing(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
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
    act_items = [{"title": a["summary"], "detail": f"{a['actor_name']} · {rel_time(a['created_at'])}", "tone": "neutral"} for a in acts]
    b["what_changed"] = act_items + list(b.get("what_changed", []))
    day = datetime.now(timezone.utc).date().isoformat()
    ups = await db.updates.find({"workspace_id": c["workspace_id"], "day": day}, {"_id": 0}).sort("updated_at", -1).to_list(50)
    b["team_updates"] = [{"user_name": u.get("user_name"), "text": u.get("text"),
                          "blocker": u.get("blocker", False), "mood": u.get("mood"),
                          "ago": rel_time(u.get("updated_at", ""))} for u in ups]
    return {**b, "is_pro": is_pro, "ai_summary": b.get("ai_summary") if is_pro else None}


@router.get("/activities")
async def list_activities(principal=Depends(get_principal)):
    acts = await db.activities.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("created_at", -1).to_list(40)
    for a in acts:
        a["ago"] = rel_time(a["created_at"])
    return {"activities": acts}


@router.post("/briefing/generate")
async def generate_briefing(principal=Depends(require_pro_perm("briefing:generate"))):
    c = await get_ws(principal["workspace_id"])
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


@router.get("/decisions")
async def decisions(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    return {"decisions": c["decisions"], "is_pro": workspace_is_pro(c), "can_act": "decisions:act" in perms_for(principal["pack"])}


class DecisionAction(BaseModel):
    action: str
    owner: Optional[str] = None


@router.post("/decisions/{decision_id}/action")
async def decision_action(decision_id: str, payload: DecisionAction, principal=Depends(require_pro_perm("decisions:act"))):
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


@router.post("/decisions")
async def create_decision(payload: DecisionInput, principal=Depends(require_pro_perm("decisions:act"))):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    c = await get_ws(principal["workspace_id"])
    d = {"id": f"d_{uuid.uuid4().hex[:8]}", "status": "pending", "owner": None, **_decision_fields(payload)}
    decisions = c["decisions"] + [d]
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    await log_activity(principal, "decisions", "decision.create", f"New decision: {d['title']}")
    return {"ok": True, "decision": d}


@router.patch("/decisions/{decision_id}")
async def edit_decision(decision_id: str, payload: DecisionInput, principal=Depends(require_pro_perm("decisions:act"))):
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


@router.delete("/decisions/{decision_id}")
async def delete_decision(decision_id: str, principal=Depends(require_pro_perm("decisions:act"))):
    c = await get_ws(principal["workspace_id"])
    decisions = [d for d in c["decisions"] if d["id"] != decision_id]
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"decisions": decisions}})
    return {"ok": True}


@router.get("/onboarding/checklist")
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
