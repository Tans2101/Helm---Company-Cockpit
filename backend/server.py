import os
import uuid
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest, CheckoutStatusResponse,
)

from seed_data import build_seed

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
PRO_PRICE = 149.0

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kalun")


# ------------------------- Auth helpers -------------------------
async def get_current_user(request: Request):
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


async def get_company():
    company = await db.company.find_one({"company_id": "kalun-demo"}, {"_id": 0})
    return company


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
        await db.users.update_one({"user_id": user_id}, {"$set": {
            "name": data.get("name"), "picture": data.get("picture")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": data.get("name"),
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    session_token = data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(
        key="session_token", value=session_token, httponly=True,
        secure=True, samesite="none", path="/", max_age=7 * 24 * 60 * 60,
    )
    return {"ok": True, "user_id": user_id, "email": email}


@api_router.get("/auth/me")
async def auth_me(user=Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"],
            "name": user.get("name"), "picture": user.get("picture")}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ------------------------- Company / data routes -------------------------
@api_router.get("/company")
async def company(user=Depends(get_current_user)):
    c = await get_company()
    return {
        "name": c["name"], "plan": c["plan"], "stage": c["stage"],
        "employees": c["employees"], "founded": c["founded"],
        "mission": c["mission"], "ceo_name": user.get("name") or "CEO",
    }


@api_router.get("/briefing")
async def briefing(user=Depends(get_current_user)):
    c = await get_company()
    b = c["briefing"]
    is_pro = c["plan"] == "pro"
    return {**b, "is_pro": is_pro, "ai_summary": b.get("ai_summary") if is_pro else None}


@api_router.post("/briefing/generate")
async def generate_briefing(user=Depends(get_current_user)):
    c = await get_company()
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    b = c["briefing"]
    context = {
        "company": c["name"], "metrics": b["metrics"],
        "what_changed": b["what_changed"], "decisions": b["what_to_decide"],
        "financials": {k: c["financials"][k] for k in ["mrr", "arr", "runway_months", "burn", "cash"]},
    }
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"briefing-{user['user_id']}",
        system_message=(
            "You are Kalun, an executive chief-of-staff AI for a startup CEO. "
            "Write a crisp morning briefing in 3-4 sentences. Synthesis over raw data, "
            "signal over noise. Lead with what matters most, name the single most "
            "important decision, and end with a confident recommendation. No fluff, no lists."
        ),
    ).with_model("anthropic", "claude-sonnet-4-6")
    msg = UserMessage(text=f"Company data for today:\n{json.dumps(context, indent=2)}\n\nWrite the CEO's morning briefing.")
    text = await chat.send_message(msg)
    await db.company.update_one({"company_id": "kalun-demo"},
                                {"$set": {"briefing.ai_summary": text}})
    return {"ai_summary": text}


@api_router.get("/decisions")
async def decisions(user=Depends(get_current_user)):
    c = await get_company()
    return {"decisions": c["decisions"], "is_pro": c["plan"] == "pro"}


class DecisionAction(BaseModel):
    action: str  # approved | rejected | delegated
    owner: Optional[str] = None


@api_router.post("/decisions/{decision_id}/action")
async def decision_action(decision_id: str, payload: DecisionAction, user=Depends(get_current_user)):
    c = await get_company()
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
    await db.company.update_one({"company_id": "kalun-demo"}, {"$set": {"decisions": decisions}})
    return {"ok": True, "decisions": decisions}


@api_router.get("/telemetry")
async def telemetry(user=Depends(get_current_user)):
    c = await get_company()
    return c["telemetry"]


@api_router.get("/financials")
async def financials(user=Depends(get_current_user)):
    c = await get_company()
    return c["financials"]


@api_router.get("/tasks")
async def tasks(user=Depends(get_current_user)):
    c = await get_company()
    return c["tasks"]


class TaskMove(BaseModel):
    column: str


@api_router.patch("/tasks/{task_id}")
async def move_task(task_id: str, payload: TaskMove, user=Depends(get_current_user)):
    c = await get_company()
    t = c["tasks"]
    for item in t["items"]:
        if item["id"] == task_id:
            item["column"] = payload.column
            break
    await db.company.update_one({"company_id": "kalun-demo"}, {"$set": {"tasks": t}})
    return {"ok": True}


@api_router.get("/reports")
async def reports(user=Depends(get_current_user)):
    c = await get_company()
    return {"reports": c["reports"], "is_pro": c["plan"] == "pro"}


@api_router.post("/reports/weekly-pack")
async def weekly_pack(user=Depends(get_current_user)):
    c = await get_company()
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required")
    context = {
        "company": c["name"],
        "financials": {k: c["financials"][k] for k in ["mrr", "arr", "runway_months", "burn"]},
        "kpis": c["telemetry"]["kpis"],
        "reports": [{"title": r["title"], "summary": r["summary"]} for r in c["reports"]],
    }
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"pack-{user['user_id']}",
        system_message=(
            "You are Kalun, writing the Weekly CEO Pack. Produce a board-ready weekly "
            "summary in markdown with sections: Headline, Growth, Financial Health, "
            "Risks, and This Week's Focus. Be concise, executive, and specific."
        ),
    ).with_model("anthropic", "claude-sonnet-4-6")
    text = await chat.send_message(UserMessage(text=f"Data:\n{json.dumps(context, indent=2)}\n\nWrite the Weekly CEO Pack."))
    return {"content": text}


@api_router.get("/team")
async def team(user=Depends(get_current_user)):
    c = await get_company()
    return c["team"]


@api_router.get("/calendar")
async def calendar(user=Depends(get_current_user)):
    c = await get_company()
    return c["calendar"]


@api_router.get("/people")
async def people(user=Depends(get_current_user)):
    c = await get_company()
    return c["people"]


@api_router.get("/integrations")
async def integrations(user=Depends(get_current_user)):
    c = await get_company()
    return {"integrations": c["integrations"], "is_pro": c["plan"] == "pro"}


@api_router.post("/integrations/{integration_id}/toggle")
async def toggle_integration(integration_id: str, user=Depends(get_current_user)):
    c = await get_company()
    if c["plan"] != "pro":
        raise HTTPException(status_code=403, detail="Pro required for live integrations")
    ints = c["integrations"]
    for i in ints:
        if i["id"] == integration_id:
            i["connected"] = not i["connected"]
            break
    await db.company.update_one({"company_id": "kalun-demo"}, {"$set": {"integrations": ints}})
    return {"ok": True, "integrations": ints}


# ------------------------- Ask Kalun (chat) -------------------------
class AskInput(BaseModel):
    message: str


@api_router.get("/ask/history")
async def ask_history(user=Depends(get_current_user)):
    msgs = await db.chat_messages.find(
        {"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


@api_router.post("/ask")
async def ask_kalun(payload: AskInput, user=Depends(get_current_user)):
    c = await get_company()
    is_pro = c["plan"] == "pro"
    if not is_pro:
        today = datetime.now(timezone.utc).date().isoformat()
        count = await db.chat_messages.count_documents(
            {"user_id": user["user_id"], "role": "user", "day": today})
        if count >= 5:
            raise HTTPException(status_code=402, detail="Free plan limited to 5 messages/day. Upgrade to Pro for unlimited.")

    now = datetime.now(timezone.utc)
    await db.chat_messages.insert_one({
        "user_id": user["user_id"], "role": "user", "content": payload.message,
        "created_at": now.isoformat(), "day": now.date().isoformat(),
    })

    context = {
        "company": c["name"], "stage": c["stage"], "employees": c["employees"],
        "financials": {k: c["financials"][k] for k in ["mrr", "arr", "runway_months", "burn", "cash", "gross_margin"]},
        "kpis": c["telemetry"]["kpis"],
        "open_decisions": [d["title"] for d in c["decisions"] if d["status"] == "pending"],
        "risks": c["telemetry"]["risks"],
    }
    history = await db.chat_messages.find(
        {"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(20)

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"ask-{user['user_id']}",
        system_message=(
            "You are Kalun, the CEO's executive AI chief-of-staff for "
            f"{c['name']} (a {c['stage']} startup, {c['employees']} people). "
            "Answer like a sharp, trusted operator: direct, quantified, decisive. "
            "Use the live company data provided. Synthesis over raw data, signal over noise. "
            "Keep answers tight. Here is the current company snapshot:\n"
            f"{json.dumps(context, indent=2)}"
        ),
    ).with_model("anthropic", "claude-sonnet-4-6")
    # replay prior history (excluding the message we just stored) into the session
    for m in history[:-1]:
        if m["role"] == "user":
            chat.messages = getattr(chat, "messages", [])

    async def gen():
        collected = ""
        try:
            from emergentintegrations.llm.chat import TextDelta, StreamDone
            async for ev in chat.stream_message(UserMessage(text=payload.message)):
                if isinstance(ev, TextDelta):
                    collected += ev.content
                    yield ev.content
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:  # noqa
            logger.exception("chat stream error")
            if not collected:
                collected = "I hit an error reaching my reasoning engine. Please try again."
                yield collected
        finally:
            await db.chat_messages.insert_one({
                "user_id": user["user_id"], "role": "assistant", "content": collected,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "day": datetime.now(timezone.utc).date().isoformat(),
            })

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------- Payments (Stripe Flow B) -------------------------
class CheckoutInput(BaseModel):
    origin_url: str


def get_stripe(request: Request) -> StripeCheckout:
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


@api_router.get("/billing/plans")
async def billing_plans(user=Depends(get_current_user)):
    c = await get_company()
    return {"current_plan": c["plan"], "pro_price": PRO_PRICE}


@api_router.post("/payments/checkout")
async def create_checkout(payload: CheckoutInput, request: Request, user=Depends(get_current_user)):
    stripe_checkout = get_stripe(request)
    success_url = f"{payload.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{payload.origin_url}/payment/cancel"
    req = CheckoutSessionRequest(
        amount=PRO_PRICE, currency="usd",
        success_url=success_url, cancel_url=cancel_url,
        metadata={"user_id": user["user_id"], "plan": "pro"},
    )
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "session_id": session.session_id, "user_id": user["user_id"],
        "amount": PRO_PRICE, "currency": "usd", "plan": "pro",
        "status": "initiated", "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"checkout_url": session.url, "session_id": session.session_id}


@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            stripe_checkout = get_stripe(request)
            status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
            if status.payment_status == "paid" or status.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "updated_at": datetime.now(timezone.utc).isoformat()}})
                if record.get("user_id"):
                    await db.company.update_one({"company_id": "kalun-demo"}, {"$set": {"plan": "pro"}})
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except Exception:
            pass
    return {"session_id": record["session_id"], "status": record["status"],
            "payment_status": record["payment_status"]}


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    stripe_checkout = get_stripe(request)
    try:
        result = await stripe_checkout.handle_webhook(body, request.headers.get("Stripe-Signature"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result.session_id and result.payment_status == "paid":
        await db.payment_transactions.update_one(
            {"session_id": result.session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": "paid",
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        await db.company.update_one({"company_id": "kalun-demo"}, {"$set": {"plan": "pro"}})
    return {"status": "ok"}


# ------------------------- Demo helpers -------------------------
@api_router.post("/demo/reset-plan")
async def reset_plan(user=Depends(get_current_user)):
    await db.company.update_one({"company_id": "kalun-demo"}, {"$set": {"plan": "free"}})
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"service": "Kalun CEO Operating System"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    existing = await db.company.find_one({"company_id": "kalun-demo"})
    if not existing:
        await db.company.insert_one(build_seed())
        logger.info("Seeded demo company")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
