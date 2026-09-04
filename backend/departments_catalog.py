"""Fixed department catalog — not stored per workspace.

Future department-specific feature collections should follow the
`{department}_stages` naming convention used by `production_stages`
(e.g. `legal_stages`, `procurement_stages`). Do not create those
collections here — only document the pattern for later prompts.
"""
from __future__ import annotations

from typing import Any, Optional

# Canonical type ids (slugs). Stable API keys — never rename lightly.
TYPE_PROCUREMENT = "procurement"
TYPE_PRODUCTION = "production"
TYPE_ACCOUNTING_FINANCE = "accounting_finance"
TYPE_SALES = "sales"
TYPE_LEGAL = "legal"
TYPE_HR = "hr"
TYPE_ENGINEERING_MAINTENANCE = "engineering_maintenance"

DEPARTMENT_CATALOG: list[dict[str, Any]] = [
    {
        "type": TYPE_PROCUREMENT,
        "name": "Procurement",
        "icon": "package",
    },
    {
        "type": TYPE_PRODUCTION,
        "name": "Production",
        "icon": "factory",
    },
    {
        "type": TYPE_ACCOUNTING_FINANCE,
        "name": "Accounting & Finance",
        "icon": "landmark",
    },
    {
        "type": TYPE_SALES,
        "name": "Sales",
        "icon": "briefcase",
    },
    {
        "type": TYPE_LEGAL,
        "name": "Legal",
        "icon": "scale",
    },
    {
        "type": TYPE_HR,
        "name": "HR",
        "icon": "users",
    },
    {
        "type": TYPE_ENGINEERING_MAINTENANCE,
        "name": "Engineering & Maintenance",
        "icon": "wrench",
    },
]

CATALOG_BY_TYPE = {d["type"]: d for d in DEPARTMENT_CATALOG}
VALID_DEPARTMENT_TYPES = frozenset(CATALOG_BY_TYPE.keys())

DEPARTMENT_MEMBER_ROLES = frozenset({"member", "lead"})


def catalog_entry(dept_type: str) -> Optional[dict[str, Any]]:
    return CATALOG_BY_TYPE.get(dept_type)


def default_name(dept_type: str) -> str:
    entry = catalog_entry(dept_type)
    return entry["name"] if entry else dept_type
