import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import llm as helm_llm
from db import db
from deps import get_principal, get_ws, require_pro_perm
from helpers import compute_financials

logger = logging.getLogger("helm")

router = APIRouter()

# ------------------------- Ask Helm -------------------------
class AskInput(BaseModel):
    message: str


@router.get("/ask/history")
async def ask_history(principal=Depends(get_principal)):
    msgs = await db.chat_messages.find({"workspace_id": principal["workspace_id"], "user_id": principal["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


@router.post("/ask")
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


router.add_api_route("/ai/ask-helm", ask_helm, methods=["POST"])
router.add_api_route("/ai/ask-kalun", ask_helm, methods=["POST"])
