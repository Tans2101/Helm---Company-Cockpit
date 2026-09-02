import uuid
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends

import quickbooks as qb_sync
from db import (
    APP_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    QB_CLIENT_ID,
    QB_CLIENT_SECRET,
    db,
)
from deps import (
    _sign_state,
    get_principal,
    get_ws,
    perms_for,
    require_pro_perm,
    workspace_is_pro,
)
from helm_config import public_api_origin
from helpers import log_activity

logger = logging.getLogger("helm")

router = APIRouter()

GOOGLE_SCOPES = [
    "openid", "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.readonly",
    # gmail.readonly omitted — re-add only when email-forward document intake ships
    # (bills forwarded to a workspace address, parsed like uploaded documents).
]


def _oauth_callback_uri(provider: str) -> str:
    return f"{public_api_origin()}/api/oauth/{provider}/callback"


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


@router.get("/integrations")
async def integrations(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    ints = []
    for i in c["integrations"]:
        item = dict(i)
        if i.get("provider") == "google":
            item["connected"] = bool(c.get("google_tokens"))
            item["configured"] = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
        elif i.get("provider") == "quickbooks":
            item["connected"] = bool(c.get("quickbooks_tokens"))
            item["configured"] = bool(QB_CLIENT_ID and QB_CLIENT_SECRET)
            item["last_synced_at"] = c.get("qb_last_synced_at")
        else:
            item["configured"] = True
        ints.append(item)
    return {"integrations": ints, "is_pro": workspace_is_pro(c), "can_manage": "integrations:manage" in perms_for(principal["pack"])}


@router.post("/integrations/{integration_id}/toggle")
async def toggle_integration(integration_id: str, principal=Depends(require_pro_perm("integrations:manage"))):
    c = await get_ws(principal["workspace_id"])
    ints = c["integrations"]
    for i in ints:
        if i["id"] == integration_id:
            if i.get("oauth"):
                raise HTTPException(status_code=400, detail="Use Connect to link this provider via OAuth")
            i["connected"] = not i["connected"]
            break
    await db.workspaces.update_one({"workspace_id": c["workspace_id"]}, {"$set": {"integrations": ints}})
    return {"ok": True, "integrations": ints}


@router.get("/integrations/{provider}/connect")
async def integration_connect(provider: str, request: Request, principal=Depends(require_pro_perm("integrations:manage"))):
    cfg = _provider_config(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not cfg["configured"]:
        return {"configured": False, "message": f"{provider.title()} OAuth credentials are not set yet. Add them in the backend .env to enable live connection."}
    params = {"client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "response_type": "code",
              "scope": cfg["scope"], "state": _sign_state(provider, principal["workspace_id"]), **cfg.get("extra", {})}
    return {"configured": True, "authorization_url": f"{cfg['auth_uri']}?{urlencode(params)}"}




@router.post("/integrations/{provider}/disconnect")
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
@router.post("/integrations/quickbooks/sync")
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


@router.get("/integrations/google/calendar-events")
async def google_calendar_events(principal=Depends(get_principal)):
    c = await get_ws(principal["workspace_id"])
    tokens = c.get("google_tokens")
    if not tokens:
        raise HTTPException(status_code=400, detail="Google not connected")
    token = tokens.get("access_token")
    async with httpx.AsyncClient() as hc:
        r = await hc.get("https://www.googleapis.com/calendar/v3/calendars/primary/events",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"timeMin": datetime.now(timezone.utc).isoformat(), "maxResults": 20, "singleEvents": True, "orderBy": "startTime"})
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="Google token expired — reconnect")
    return {"events": r.json().get("items", [])}
