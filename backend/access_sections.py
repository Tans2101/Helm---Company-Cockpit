"""Department-based section access — CEO configures which departments can edit each area."""

DEFAULT_DEPARTMENTS = [
    "Engineering",
    "Product",
    "Sales",
    "Marketing",
    "Finance",
    "Operations",
    "Support",
    "HR",
    "Growth",
    "General",
]

# Sections the CEO can grant department write access to (beyond access packs).
MANAGEABLE_SECTIONS = [
    {"id": "financials", "label": "Financials", "perm": "finance:write",
     "description": "Revenue, expenses, runway, and document uploads."},
    {"id": "people", "label": "People", "perm": "people:write",
     "description": "Team roster and headcount."},
    {"id": "sales", "label": "Pipeline", "perm": "sales:write",
     "description": "Deals, stages, and pipeline value."},
    {"id": "reports", "label": "Reports", "perm": "reports:write",
     "description": "Manual reports and weekly CEO pack inputs."},
    {"id": "tasks", "label": "Tasks", "perm": "tasks:assign",
     "description": "Create tasks and assign work to teammates."},
    {"id": "decisions", "label": "Decisions", "perm": "decisions:act",
     "description": "Approve, delegate, or reject decision cards."},
    {"id": "telemetry", "label": "Telemetry", "perm": "telemetry:write",
     "description": "KPI notes, risk radar, and manual telemetry inputs."},
]

_SECTION_PERM = {s["id"]: s["perm"] for s in MANAGEABLE_SECTIONS}


def section_pack_perm(section_id: str) -> str:
    return _SECTION_PERM.get(section_id, "")


def normalize_section_access(raw: dict | None) -> dict:
    """Ensure section_access only contains known section ids and string department lists."""
    if not raw:
        return {}
    out = {}
    valid = set(_SECTION_PERM.keys())
    for section_id, depts in raw.items():
        if section_id not in valid or not isinstance(depts, list):
            continue
        cleaned = sorted({str(d).strip() for d in depts if str(d).strip()})
        if cleaned:
            out[section_id] = cleaned
    return out
