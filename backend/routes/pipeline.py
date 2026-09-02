import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db import db
from deps import get_principal, require_pro_perm, perms_for
from helpers import compute_financials, fmt_money, log_activity

router = APIRouter()

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


@router.get("/deals")
async def list_deals(principal=Depends(get_principal)):
    deals = await db.deals.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"deals": deals, "can_write": "sales:write" in perms_for(principal["pack"]),
            "metrics": _deal_metrics(deals), "stages": [{"id": s, "label": STAGE_LABEL[s]} for s in DEAL_STAGES]}


@router.post("/deals")
async def create_deal(payload: DealInput, principal=Depends(require_pro_perm("sales:write"))):
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


@router.patch("/deals/{deal_id}")
async def update_deal(deal_id: str, payload: DealInput, principal=Depends(require_pro_perm("sales:write"))):
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


@router.delete("/deals/{deal_id}")
async def delete_deal(deal_id: str, principal=Depends(require_pro_perm("sales:write"))):
    await db.deals.delete_one({"id": deal_id, "workspace_id": principal["workspace_id"]})
    return {"ok": True}


@router.get("/telemetry")
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
