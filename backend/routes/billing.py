import uuid
import json
import hmac
import hashlib
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends

from db import (
    BILLING_ENFORCED,
    DEMO_RESET_ENABLED,
    PADDLE_API_BASE,
    PADDLE_API_KEY,
    PADDLE_CLIENT_TOKEN,
    PADDLE_ENV,
    PADDLE_PRICE_ID,
    PADDLE_WEBHOOK_SECRET,
    PRO_PRICE,
    db,
)
from deps import get_principal, get_ws, perms_for, require

logger = logging.getLogger("helm")

router = APIRouter()

# ------------------------- Payments -------------------------
async def get_billing_status(workspace_id: str, pack: str):
    c = await get_ws(workspace_id)
    sub_status = c.get("subscription_status") or c.get("billing_status")
    has_customer = bool(c.get("paddle_customer_id"))
    return {
        "current_plan": c["plan"],
        "pro_only": True,
        "billing_enforced": BILLING_ENFORCED,
        "requires_activation": BILLING_ENFORCED and c["plan"] != "pro",
        "pro_price": PRO_PRICE,
        "price": PRO_PRICE,
        "can_manage": "billing:manage" in perms_for(pack),
        "paddle_ready": bool(PADDLE_CLIENT_TOKEN and PADDLE_PRICE_ID),
        "subscription_status": sub_status,
        "billing_provider": c.get("billing_provider"),
        "portal_available": has_customer and bool(PADDLE_API_KEY),
        "demo_reset_enabled": DEMO_RESET_ENABLED,
        "canceled_at": c.get("canceled_at"),
    }


@router.get("/billing/plans")
async def billing_plans(principal=Depends(get_principal)):
    return await get_billing_status(principal["workspace_id"], principal["pack"])


@router.get("/billing/status")
async def billing_status(principal=Depends(get_principal)):
    return await get_billing_status(principal["workspace_id"], principal["pack"])


@router.post("/demo/reset-plan")
async def reset_plan(principal=Depends(require("billing:manage"))):
    if not DEMO_RESET_ENABLED:
        raise HTTPException(status_code=403, detail="Demo reset is disabled")
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]}, {
        "$set": {"plan": "free", "subscription_status": None, "billing_status": None},
        "$unset": {"paddle_subscription_id": "", "paddle_customer_id": ""},
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


@router.post("/billing/paddle/config")
async def paddle_config(principal=Depends(require("billing:manage"))):
    if not (PADDLE_CLIENT_TOKEN and PADDLE_PRICE_ID):
        raise HTTPException(status_code=400, detail="Paddle is not configured")
    nonce = uuid.uuid4().hex
    await db.paddle_intents.insert_one({
        "_id": nonce, "workspace_id": principal["workspace_id"], "user_id": principal["user_id"],
        "price_id": PADDLE_PRICE_ID, "used": False, "created_at": datetime.now(timezone.utc),
    })
    return {"client_token": PADDLE_CLIENT_TOKEN, "price_id": PADDLE_PRICE_ID,
            "environment": PADDLE_ENV, "checkout_nonce": nonce,
            "workspace_id": principal["workspace_id"], "user_id": principal["user_id"],
            "email": principal.get("email")}


async def _paddle_provision(event):
    data = event.get("data") or {}
    custom = data.get("custom_data") or {}
    nonce = custom.get("checkout_nonce")
    workspace_id = custom.get("workspace_id")
    user_id = custom.get("user_id")
    if not (nonce and workspace_id and user_id):
        return
    intent = await db.paddle_intents.find_one({"_id": nonce})
    if not intent or intent.get("workspace_id") != workspace_id or intent.get("user_id") != user_id:
        return
    await db.workspaces.update_one({"workspace_id": workspace_id}, {"$set": {
        "plan": "pro", "billing_provider": "paddle",
        "paddle_subscription_id": data.get("subscription_id") or data.get("id"),
        "paddle_customer_id": data.get("customer_id"),
        "paddle_last_event_at": event.get("occurred_at"),
        "subscription_status": "active", "billing_status": "active",
    }, "$unset": {"canceled_at": ""}})
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


@router.post("/payments/paddle/portal")
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


@router.post("/webhook/paddle")
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
        await _paddle_provision(event)
    elif event_type in ("subscription.created", "subscription.activated", "subscription.updated"):
        if (event.get("data") or {}).get("status") == "active":
            await _paddle_provision(event)
    elif event_type in ("subscription.canceled", "subscription.cancelled"):
        await _paddle_downgrade(event, "canceled")
    elif event_type == "subscription.paused":
        await _paddle_downgrade(event, "paused")
    elif event_type in ("subscription.past_due", "subscription.past-due"):
        await _paddle_downgrade(event, "past_due")
    return {"received": True}
