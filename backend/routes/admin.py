import os
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, Depends

import clerk_auth
from db import (
    CLERK_PUBLISHABLE_KEY,
    FRONTEND_URL,
    MONGO_SOURCE,
    _mongo_candidate_urls,
    _make_mongo_client,
    _mongo_source_label,
    _redact_mongo_url,
    mongo_ping,
    mongo_url,
    db,
)
from deps import (
    _require_setup_secret,
    get_user,
    pack_of,
    require,
)

logger = logging.getLogger("helm")

router = APIRouter()

# ------------------------- GDPR / account -------------------------
_WORKSPACE_COLLECTIONS = (
    "financial_entries", "deals", "activities", "updates", "chat_messages",
    "paddle_intents", "payment_transactions",
)


def _strip_sensitive(doc: dict) -> dict:
    if not doc:
        return doc
    out = {k: v for k, v in doc.items() if k not in (
        "password", "password_hash", "oauth_session_token_enc",
        "google_tokens", "quickbooks_tokens",
    )}
    return out


@router.get("/account/export")
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


@router.delete("/account")
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


@router.delete("/workspace")
async def delete_workspace(principal=Depends(require("billing:manage"))):
    return await _delete_workspace_handler(principal)


@router.delete("/workspaces/current")
async def delete_workspace_current(principal=Depends(require("billing:manage"))):
    return await _delete_workspace_handler(principal)


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


@router.get("/setup/status")
async def setup_status():
    """Production readiness probe — no secrets."""
    mongo_ok = await mongo_ping()
    probes = await _probe_mongo_candidates()
    clerk_sync = clerk_auth.clerk_sync_status()
    return {
        "frontend_url": FRONTEND_URL or None,
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
    }


@router.get("/setup/google-oauth")
async def setup_google_oauth():
    """Clerk Google OAuth readiness — verifies redirect URI is registered in Google Cloud."""
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    return await clerk_auth.clerk_google_oauth_status()


@router.post("/setup/clerk-sync")
async def setup_clerk_sync(request: Request):
    """Force Clerk instance sync (allowed_origins + development_origin for Vercel)."""
    _require_setup_secret(request)
    if not clerk_auth.clerk_configured():
        raise HTTPException(status_code=400, detail="Clerk is not configured")
    result = await clerk_auth.sync_clerk_instance()
    if not result.get("synced"):
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/health")
async def health():
    """Liveness probe for Render — must return 200 within 5s even when Mongo is down."""
    mongo_ok = await mongo_ping()
    return {"status": "ok", "mongo": mongo_ok, "mongo_source": MONGO_SOURCE}


@router.get("/")
async def root():
    return {"service": "Helm CEO Operating System"}
