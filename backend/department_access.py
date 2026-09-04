"""Department membership helpers — reusable by department-scoped endpoints."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("helm")


def is_workspace_ceo(principal: dict) -> bool:
    """Owner pack / role = company CEO for department admin actions."""
    return principal.get("pack") == "owner" or principal.get("role") == "owner"


async def get_department_membership(db, department_id: str, user_id: str) -> Optional[dict]:
    return await db.department_members.find_one(
        {"department_id": department_id, "user_id": user_id},
        {"_id": 0},
    )


async def is_department_member(db, user_id: str, department_id: str) -> bool:
    row = await get_department_membership(db, department_id, user_id)
    return bool(row)


async def is_department_lead(db, user_id: str, department_id: str) -> bool:
    row = await get_department_membership(db, department_id, user_id)
    return bool(row) and row.get("role") == "lead"


async def can_manage_department_members(db, principal: dict, department_id: str) -> bool:
    if is_workspace_ceo(principal):
        return True
    return await is_department_lead(db, principal["user_id"], department_id)


async def can_access_department(db, principal: dict, department: dict) -> bool:
    """CEO sees every enabled department; others need a membership row."""
    if is_workspace_ceo(principal):
        return True
    return await is_department_member(db, principal["user_id"], department["department_id"])


async def accessible_department_ids(
    db, principal: dict, dept_type: str,
) -> Optional[list[str]]:
    """Department ids of ``dept_type`` the principal may read records from.

    Returns ``None`` for CEO (bypass — see all workspace records of that kind).
    Returns a list (possibly empty) for everyone else — empty means no access.
    """
    if is_workspace_ceo(principal):
        return None
    rows = await db.departments.find(
        {
            "workspace_id": principal["workspace_id"],
            "type": dept_type,
            "enabled": True,
        },
        {"_id": 0, "department_id": 1},
    ).to_list(50)
    if not rows:
        return []
    my_rows = await db.department_members.find(
        {
            "user_id": principal["user_id"],
            "department_id": {"$in": [r["department_id"] for r in rows]},
        },
        {"_id": 0, "department_id": 1},
    ).to_list(50)
    return [m["department_id"] for m in my_rows]


def apply_department_filter(base_filter: dict, department_ids: Optional[list[str]]) -> dict:
    """Attach department_id constraint. ``None`` = CEO bypass (unchanged filter)."""
    if department_ids is None:
        return base_filter
    out = dict(base_filter)
    out["department_id"] = {"$in": list(department_ids)}
    return out


# Feature collections owned by a department — cleared when the department is disabled.
# Do NOT include deals / financial_entries: those are core workspace data that keep
# their department_id but must not permanently block disable.
DEPARTMENT_FEATURE_COLLECTIONS = (
    "production_stages",
    "procurement_requests",
    "legal_matters",
    "maintenance_tickets",
    "hr_onboarding_instances",
    "hr_onboarding_template",
)

# Back-compat alias used by older call sites / tests.
DEPARTMENT_DEPENDENT_COLLECTIONS = DEPARTMENT_FEATURE_COLLECTIONS


async def department_has_dependent_data(db, department_id: str) -> bool:
    """True if any department-specific feature data exists under this department."""
    for name in DEPARTMENT_FEATURE_COLLECTIONS:
        coll = getattr(db, name, None)
        if coll is None:
            continue
        try:
            found = await coll.find_one({"department_id": department_id}, {"_id": 1})
        except Exception:
            continue
        if found:
            return True
    return False


async def clear_department_feature_data(db, department_id: str) -> dict[str, int]:
    """Delete all feature rows for a department. Returns {collection: deleted_count}."""
    cleared: dict[str, int] = {}
    # Best-effort cleanup of legal matter files in R2 before wiping rows.
    legal = getattr(db, "legal_matters", None)
    if legal is not None:
        try:
            rows = await legal.find(
                {"department_id": department_id},
                {"_id": 0, "document_ref": 1},
            ).to_list(5000)
        except Exception:
            rows = []
        if rows:
            try:
                import storage as doc_storage
                if doc_storage.r2_configured():
                    import asyncio
                    for row in rows:
                        ref = row.get("document_ref") or {}
                        key = ref.get("storage_key") if isinstance(ref, dict) else None
                        if key:
                            try:
                                await asyncio.to_thread(doc_storage.delete_document, key)
                            except Exception:
                                logger.exception("failed to delete legal doc %s on dept clear", key)
            except Exception:
                logger.exception("legal matter R2 cleanup skipped")

    for name in DEPARTMENT_FEATURE_COLLECTIONS:
        coll = getattr(db, name, None)
        if coll is None:
            continue
        try:
            res = await coll.delete_many({"department_id": department_id})
            cleared[name] = int(getattr(res, "deleted_count", 0) or 0)
        except Exception:
            logger.exception("failed clearing %s for department %s", name, department_id)
            cleared[name] = 0
    return cleared
