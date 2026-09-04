"""Fixed department catalog — not stored per workspace.

Future department-specific feature collections (when built) must follow the
`{department}_stages` naming convention established by `production_stages`:

  - production_stages              (exists — Production chain)
  - procurement_requests           (exists — Procurement request queue)
  - procurement_stages             (unused; Procurement uses a request queue, not a chain)
  - legal_matters                  (exists — Legal matter queue)
  - legal_stages                   (unused; Legal uses a matter queue, not a chain)
  - maintenance_tickets            (exists — Engineering & Maintenance ticket queue)
  - engineering_maintenance_stages (unused; Eng & Maint uses a ticket queue, not a chain)
  - hr_stages                      (future)
  - sales_stages                   (future, if needed beyond Pipeline)
  - accounting_finance_stages      (future, if needed beyond Financials)

Do not create these collections here — only document the pattern so later
prompts extend a consistent shape instead of inventing a new one each time.
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

# Types that ship with a placeholder shell until their dedicated feature prompt.
PLACEHOLDER_SHELL_TYPES = frozenset({
    TYPE_HR,
})

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


def stages_collection_name(dept_type: str) -> str:
    """Reserved collection name for a department's future stages feature."""
    return f"{dept_type}_stages"
