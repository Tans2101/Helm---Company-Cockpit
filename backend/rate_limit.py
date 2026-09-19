"""Mongo-backed per-workspace rate limits for document upload/extract and insights."""
from __future__ import annotations

import os
from datetime import datetime, timezone

DOC_UPLOAD_HOURLY_LIMIT = int(os.environ.get("DOC_UPLOAD_HOURLY_LIMIT", "30"))
DOC_EXTRACT_HOURLY_LIMIT = int(
    os.environ.get("DOC_EXTRACT_HOURLY_LIMIT", str(DOC_UPLOAD_HOURLY_LIMIT))
)
# Decision/delegate suggestion regeneration — heavier multi-call AI work.
INSIGHTS_DAILY_LIMIT = int(os.environ.get("INSIGHTS_DAILY_LIMIT", "3"))
ROLLING_WINDOW_SECONDS = 3600
INSIGHTS_WINDOW_SECONDS = 86400
COLLECTION = "document_rate_events"
INSIGHTS_COLLECTION = "insights_rate_events"
ASK_HELM_COLLECTION = "ask_helm_rate_events"
ASK_HELM_WINDOW_SECONDS = 30 * 24 * 3600
ASK_HELM_FREE_MONTHLY_LIMIT = 10
# Document AI Invoice Parser is billed to Trenston's GCP project (trial credits).
# 0 disables Document AI (Claude-only). Defaults keep a small daily budget.
DOCUMENT_AI_COLLECTION = "document_ai_usage"
DOCUMENT_AI_WINDOW_SECONDS = 86400
DOCUMENT_AI_GLOBAL_DAILY_LIMIT = int(os.environ.get("DOCUMENT_AI_GLOBAL_DAILY_LIMIT", "80"))
DOCUMENT_AI_WORKSPACE_DAILY_LIMIT = int(os.environ.get("DOCUMENT_AI_WORKSPACE_DAILY_LIMIT", "8"))


async def count_events(db, workspace_id: str, action: str) -> int:
    """Count rate events in the rolling window (TTL prunes older than 1 hour)."""
    return await db.document_rate_events.count_documents({
        "workspace_id": workspace_id,
        "action": action,
    })


async def record_event(db, workspace_id: str, action: str) -> None:
    await db.document_rate_events.insert_one({
        "workspace_id": workspace_id,
        "action": action,
        "created_at": datetime.now(timezone.utc),
    })


async def is_over_limit(db, workspace_id: str, action: str, limit: int) -> bool:
    if limit <= 0:
        return False
    return await count_events(db, workspace_id, action) >= limit


async def acquire_event_slot(db, workspace_id: str, action: str, limit: int) -> bool:
    """Check+record in one step. Returns True when the caller may proceed.

    Uses a per-(workspace, action) counter with find_one_and_update so two
    concurrent requests cannot both slip under the same pre-increment count.
    """
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError

    if limit <= 0:
        await record_event(db, workspace_id, action)
        return True
    now = datetime.now(timezone.utc)
    key = f"{workspace_id}:{action}"
    coll = db.document_rate_buckets
    try:
        doc = await coll.find_one_and_update(
            {"_id": key, "count": {"$lt": limit}},
            {
                "$inc": {"count": 1},
                "$set": {"updated_at": now, "workspace_id": workspace_id, "action": action},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        doc = await coll.find_one_and_update(
            {"_id": key, "count": {"$lt": limit}},
            {"$inc": {"count": 1}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
    if not doc:
        return False
    await record_event(db, workspace_id, action)
    return True


async def count_insights_events(db, workspace_id: str) -> int:
    return await db.insights_rate_events.count_documents({"workspace_id": workspace_id})


async def record_insights_event(db, workspace_id: str) -> None:
    await db.insights_rate_events.insert_one({
        "workspace_id": workspace_id,
        "action": "generate_suggestions",
        "created_at": datetime.now(timezone.utc),
    })


async def insights_over_limit(db, workspace_id: str, limit: int = INSIGHTS_DAILY_LIMIT) -> bool:
    if limit <= 0:
        return False
    return await count_insights_events(db, workspace_id) >= limit


async def acquire_insights_slot(db, workspace_id: str, limit: int = INSIGHTS_DAILY_LIMIT) -> bool:
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError

    if limit <= 0:
        await record_insights_event(db, workspace_id)
        return True
    now = datetime.now(timezone.utc)
    key = f"insights:{workspace_id}"
    coll = db.insights_rate_buckets
    try:
        doc = await coll.find_one_and_update(
            {"_id": key, "count": {"$lt": limit}},
            {
                "$inc": {"count": 1},
                "$set": {"updated_at": now, "workspace_id": workspace_id},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        doc = await coll.find_one_and_update(
            {"_id": key, "count": {"$lt": limit}},
            {"$inc": {"count": 1}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
    if not doc:
        return False
    await record_insights_event(db, workspace_id)
    return True


async def count_ask_helm_events(db, workspace_id: str) -> int:
    return await db.ask_helm_rate_events.count_documents({"workspace_id": workspace_id})


async def record_ask_helm_event(db, workspace_id: str) -> None:
    await db.ask_helm_rate_events.insert_one({
        "workspace_id": workspace_id,
        "action": "ask",
        "created_at": datetime.now(timezone.utc),
    })


async def ask_helm_over_limit(
    db, workspace_id: str, limit: int = ASK_HELM_FREE_MONTHLY_LIMIT,
) -> bool:
    if limit <= 0:
        return False
    return await count_ask_helm_events(db, workspace_id) >= limit


async def acquire_ask_helm_slot(
    db, workspace_id: str, limit: int = ASK_HELM_FREE_MONTHLY_LIMIT,
) -> bool:
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError

    if limit <= 0:
        await record_ask_helm_event(db, workspace_id)
        return True
    now = datetime.now(timezone.utc)
    key = f"ask:{workspace_id}"
    coll = db.ask_helm_rate_buckets
    try:
        doc = await coll.find_one_and_update(
            {"_id": key, "count": {"$lt": limit}},
            {
                "$inc": {"count": 1},
                "$set": {"updated_at": now, "workspace_id": workspace_id},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        doc = await coll.find_one_and_update(
            {"_id": key, "count": {"$lt": limit}},
            {"$inc": {"count": 1}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
    if not doc:
        return False
    await record_ask_helm_event(db, workspace_id)
    return True


async def document_ai_allowed(
    db,
    workspace_id: str,
    *,
    global_limit: int = DOCUMENT_AI_GLOBAL_DAILY_LIMIT,
    workspace_limit: int = DOCUMENT_AI_WORKSPACE_DAILY_LIMIT,
) -> bool:
    """True when this extract may call Google Document AI.

    Unlike other limiters, 0 is a kill switch (skip Document AI, use Claude).
    Over-limit also skips Document AI rather than 429 the user.
    """
    if global_limit <= 0 or workspace_limit <= 0:
        return False
    global_count = await db.document_ai_usage.count_documents({})
    if global_count >= global_limit:
        return False
    ws_count = await db.document_ai_usage.count_documents({"workspace_id": workspace_id})
    return ws_count < workspace_limit


async def record_document_ai(db, workspace_id: str) -> None:
    await db.document_ai_usage.insert_one({
        "workspace_id": workspace_id,
        "created_at": datetime.now(timezone.utc),
    })
