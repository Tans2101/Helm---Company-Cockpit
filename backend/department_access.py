"""Department membership helpers — reusable by department-scoped endpoints."""
from __future__ import annotations

from typing import Optional


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


# Collections that would block disabling a department once features exist.
# Add new `{dept}_stages` (and similar) names here as department features ship.
DEPARTMENT_DEPENDENT_COLLECTIONS = (
    "production_stages",
    "procurement_requests",
    "legal_matters",
    "deals",
    "financial_entries",
)


async def department_has_dependent_data(db, department_id: str) -> bool:
    """True if any department-specific feature data exists under this department."""
    for name in DEPARTMENT_DEPENDENT_COLLECTIONS:
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
