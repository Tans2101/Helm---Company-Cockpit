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
