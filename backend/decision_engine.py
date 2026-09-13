"""Pure signal detectors for CEO decision / delegate suggestions.

Each detector takes already-fetched workspace data and returns structured
signals the LLM can draft into decision or delegate cards.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Optional

from money_fmt import fmt_money_plain
from departments_catalog import TYPE_ENGINEERING_MAINTENANCE, TYPE_HR, TYPE_PRODUCTION
from department_report_drafts import SPEC_BY_TYPE


SEVERITIES = ("high", "medium", "low")
STALLED_DEAL_DAYS = 14
STALLED_DEPARTMENT_DAYS = 5
URGENT_MAINTENANCE_DAYS = 2
RUNWAY_MONTHS_THRESHOLD = 6
BURN_INCREASE_PCT = 0.20
EXPENSE_SPIKE_PCT = 0.25
SIGNAL_CAP = 12

# Keep in sync with server._MAINT_PRIORITY_RANK — 0 is the top (most urgent) rank.
MAINT_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
MAINT_TOP_PRIORITY_RANK = min(MAINT_PRIORITY_RANK.values())

# Signals that become decision suggestions vs delegate suggestions
DECISION_SIGNAL_TYPES = frozenset({
    "runway_risk",
    "burn_increase",
    "expense_spike",
    "stalled_deal",
    # Unresolved high-priority equipment tickets may need CEO-level escalation
    # (downtime), unlike generic department stall nudges.
    "urgent_maintenance",
    # Past-due production work orders (fact check, not a forecast).
    "overdue_work_order",
})
DELEGATE_SIGNAL_TYPES = frozenset({
    "overdue_task",
    "recurring_blocker",
    "stalled_department_item",
    "stalled_onboarding",
})


def _signal(type_: str, severity: str, summary: str, detail: str, related_id=None, **extra) -> dict:
    out = {
        "type": type_,
        "severity": severity if severity in SEVERITIES else "medium",
        "summary": summary,
        "detail": detail,
        "related_id": related_id,
    }
    out.update(extra)
    return out


# ---- Shared overdue date parsing (used by detect_overdue_tasks) ----

def parse_task_due_date(due) -> Optional[date]:
    """Return a calendar date when `due` parses cleanly.

    Free-text due dates (e.g. "Wed", "This week") cannot be evaluated for overdue status.
    """
    if due is None:
        return None
    s = str(due).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def is_task_overdue(task: dict, today: Optional[date] = None) -> bool:
    if task.get("column") == "done":
        return False
    due_d = parse_task_due_date(task.get("due"))
    if due_d is None:
        return False
    today = today or datetime.now(timezone.utc).date()
    return due_d < today


def _parse_iso_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def expense_totals_by_month_category(entries: list) -> dict:
    """Build {YYYY-MM: {category: amount}} from financial_entries (expense only).

    Recurring expenses use non-overlapping rate windows (see finance_recurrence).
    """
    import finance_recurrence as fin_recur

    horizon = fin_recur.resolve_expense_horizon(entries or [])
    return fin_recur.expand_expense_category_totals(entries or [], horizon)


def detect_runway_risk(fin: dict) -> Optional[dict]:
    """Fire if runway < 6 months, or burn rose materially month over month.

    Missing cash (`cash_entered` false / `runway_months` None) is not zero runway.
    """
    if not fin or not fin.get("has_data"):
        return None
    runway = fin.get("runway_months")
    if fin.get("cash_entered") is False:
        runway = None
    burn_series = fin.get("burn_series") or []
    reasons = []
    severity = "medium"

    if runway is not None and runway < RUNWAY_MONTHS_THRESHOLD:
        reasons.append(f"runway is {runway} months (under {RUNWAY_MONTHS_THRESHOLD})")
        severity = "high" if runway < 3 else "medium"

    burn_delta_pct = None
    if len(burn_series) >= 2:
        prev = float(burn_series[-2].get("burn") or 0)
        curr = float(burn_series[-1].get("burn") or 0)
        if prev > 0 and (curr - prev) / prev >= BURN_INCREASE_PCT:
            burn_delta_pct = round((curr - prev) / prev * 100, 1)
            reasons.append(
                f"net burn rose {burn_delta_pct}% MoM "
                f"({burn_series[-2].get('month')} → {burn_series[-1].get('month')}: "
                f"{prev:.0f} → {curr:.0f})"
            )
            if severity != "high":
                severity = "high" if burn_delta_pct >= 40 else "medium"

    if not reasons:
        return None

    sig_type = "runway_risk" if (runway is not None and runway < RUNWAY_MONTHS_THRESHOLD) else "burn_increase"
    return _signal(
        sig_type,
        severity,
        summary="Cash runway / burn pressure",
        detail="; ".join(reasons) + f". Current burn {fin.get('burn')}, cash {fin.get('cash')}.",
        related_id=None,
        runway_months=runway,
        burn=fin.get("burn"),
        cash=fin.get("cash"),
        burn_delta_pct=burn_delta_pct,
    )


def detect_expense_spike(expense_by_month: dict, *, currency: str = "usd") -> list:
    """Fire per category where latest month spend is up >25% vs prior month."""
    months = sorted(expense_by_month.keys())
    if len(months) < 2:
        return []
    prev_m, curr_m = months[-2], months[-1]
    prev_cats = expense_by_month.get(prev_m) or {}
    curr_cats = expense_by_month.get(curr_m) or {}
    out = []
    for cat, curr_amt in curr_cats.items():
        prev_amt = float(prev_cats.get(cat) or 0)
        if prev_amt <= 0:
            continue
        if (curr_amt - prev_amt) / prev_amt < EXPENSE_SPIKE_PCT:
            continue
        delta_pct = round((curr_amt - prev_amt) / prev_amt * 100, 1)
        severity = "high" if delta_pct >= 50 else "medium"
        out.append(_signal(
            "expense_spike",
            severity,
            summary=f"{cat} spend up {delta_pct}% MoM",
            detail=(
                f"{cat}: {fmt_money_plain(prev_amt, currency)} in {prev_m} → "
                f"{fmt_money_plain(curr_amt, currency)} in {curr_m} "
                f"(+{delta_pct}%)."
            ),
            related_id=cat,
            category=cat,
            prev_month=prev_m,
            curr_month=curr_m,
            prev_amount=round(prev_amt, 2),
            curr_amount=round(float(curr_amt), 2),
            delta_pct=delta_pct,
        ))
    return out


def detect_stalled_deals(
    deals: list,
    *,
    now: Optional[datetime] = None,
    days: int = STALLED_DEAL_DAYS,
    currency: str = "usd",
) -> list:
    """Fire for open deals with no stage change (updated_at) in `days` days."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for d in deals or []:
        stage = d.get("stage")
        if stage in ("won", "lost"):
            continue
        updated = _parse_iso_dt(d.get("updated_at") or d.get("created_at"))
        if updated is None or updated >= cutoff:
            continue
        idle_days = (now - updated).days
        name = d.get("name") or "Untitled deal"
        value = d.get("value")
        value_s = fmt_money_plain(value, currency) if value is not None else "unknown value"
        severity = "high" if idle_days >= days * 2 else "medium"
        out.append(_signal(
            "stalled_deal",
            severity,
            summary=f"Deal stalled: {name}",
            detail=(
                f"{name} has been in stage '{stage}' for {idle_days} days "
                f"({value_s}). Last activity {updated.date().isoformat()}."
            ),
            related_id=d.get("id"),
            deal_name=name,
            stage=stage,
            value=value,
            idle_days=idle_days,
            owner_name=d.get("owner_name") or "",
        ))
    return out


def detect_overdue_tasks(tasks: list, *, today: Optional[date] = None) -> list:
    """Fire for open tasks with a parseable past due date."""
    today = today or datetime.now(timezone.utc).date()
    out = []
    for t in tasks or []:
        if not is_task_overdue(t, today):
            continue
        due_d = parse_task_due_date(t.get("due"))
        days_late = (today - due_d).days if due_d else 0
        title = t.get("title") or "Untitled task"
        assignee = t.get("assignee") or "Unassigned"
        severity = "high" if days_late >= 7 else "medium"
        out.append(_signal(
            "overdue_task",
            severity,
            summary=f"Overdue: {title}",
            detail=(
                f"Task '{title}' assigned to {assignee} was due {due_d.isoformat()} "
                f"({days_late} day(s) late), still in '{t.get('column')}'."
            ),
            related_id=t.get("id"),
            task_title=title,
            assignee_name=assignee,
            assignee_user_id=t.get("assignee_user_id"),
            due=due_d.isoformat() if due_d else t.get("due"),
            days_late=days_late,
            column=t.get("column"),
        ))
    return out


def detect_recurring_blockers(updates: list) -> list:
    """Fire when the same person flagged a blocker on 2+ consecutive calendar days.

    `updates` should cover recent days (e.g. last 7) for the workspace.
    """
    # user_id -> sorted unique days with blocker=True
    by_user: dict = {}
    names: dict = {}
    for u in updates or []:
        if not u.get("blocker"):
            continue
        uid = u.get("user_id")
        day = u.get("day")
        if not uid or not day:
            continue
        by_user.setdefault(uid, set()).add(day)
        names[uid] = u.get("user_name") or u.get("name") or uid

    out = []
    for uid, days in by_user.items():
        ordered = sorted(days)
        # Find longest consecutive streak ending at the most recent day
        streak = 1
        for i in range(len(ordered) - 1, 0, -1):
            try:
                d_cur = date.fromisoformat(ordered[i])
                d_prev = date.fromisoformat(ordered[i - 1])
            except ValueError:
                break
            if (d_cur - d_prev).days == 1:
                streak += 1
            else:
                break
        if streak < 2:
            # Also accept any 2+ consecutive pair anywhere in the window
            streak = 1
            best = 1
            for i in range(1, len(ordered)):
                try:
                    d_cur = date.fromisoformat(ordered[i])
                    d_prev = date.fromisoformat(ordered[i - 1])
                except ValueError:
                    continue
                if (d_cur - d_prev).days == 1:
                    streak += 1
                    best = max(best, streak)
                else:
                    streak = 1
            streak = best
        if streak < 2:
            continue
        name = names.get(uid, uid)
        # Grab latest blocker text if present
        latest_text = ""
        for u in sorted((x for x in updates if x.get("user_id") == uid and x.get("blocker")),
                        key=lambda x: x.get("day") or "", reverse=True):
            latest_text = (u.get("text") or "").strip()
            if latest_text:
                break
        detail = f"{name} flagged a blocker on {streak} consecutive days."
        if latest_text:
            detail += f' Latest: "{latest_text[:160]}"'
        out.append(_signal(
            "recurring_blocker",
            "high" if streak >= 3 else "medium",
            summary=f"Recurring blocker: {name}",
            detail=detail,
            related_id=uid,
            assignee_user_id=uid,
            assignee_name=name,
            streak_days=streak,
            blocker_text=latest_text,
        ))
    return out


def _item_last_activity(item: dict) -> Optional[datetime]:
    return _parse_iso_dt(item.get("updated_at") or item.get("created_at"))


def _item_label(item: dict, spec: dict) -> str:
    return (item.get(spec.get("label_field") or "name") or "").strip() or "Untitled"


def detect_stalled_department_item(
    items: list,
    spec: dict,
    *,
    threshold_days: int = STALLED_DEPARTMENT_DAYS,
    now: Optional[datetime] = None,
) -> list:
    """Flag open department records with no `updated_at` movement past `threshold_days`.

    `spec` is a `department_report_drafts.DEPT_SPECS` row (status_field, done_value, …).
    HR onboarding uses `detect_stalled_onboarding` instead.
    """
    if (spec or {}).get("type") == TYPE_HR:
        return []
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=threshold_days)
    status_field = spec["status_field"]
    done_value = spec["done_value"]
    dept_name = spec.get("name") or spec.get("type") or "Department"
    noun = spec.get("noun") or "item"
    out = []
    for item in items or []:
        status = item.get(status_field)
        if status == done_value:
            continue
        updated = _item_last_activity(item)
        if updated is None or updated >= cutoff:
            continue
        idle_days = (now - updated).days
        label = _item_label(item, spec)
        out.append(_signal(
            "stalled_department_item",
            "medium",
            summary=f"{dept_name}: {label} hasn't moved in {idle_days} days",
            detail=(
                f"{noun.capitalize()} '{label}' is still '{status}' after {idle_days} days "
                f"with no update (last activity {updated.date().isoformat()})."
            ),
            related_id=item.get("id"),
            department_type=spec.get("type"),
            department_name=dept_name,
            item_label=label,
            status=status,
            idle_days=idle_days,
        ))
    return out


def detect_urgent_maintenance(
    items: list,
    spec: dict | None = None,
    *,
    threshold_days: int = URGENT_MAINTENANCE_DAYS,
    now: Optional[datetime] = None,
) -> list:
    """Unresolved top-rank (high) maintenance tickets idle past a short window."""
    spec = spec or SPEC_BY_TYPE[TYPE_ENGINEERING_MAINTENANCE]
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=threshold_days)
    status_field = spec["status_field"]
    done_value = spec["done_value"]
    out = []
    for item in items or []:
        if item.get(status_field) == done_value:
            continue
        rank = MAINT_PRIORITY_RANK.get(str(item.get("priority") or "").lower(), 9)
        if rank != MAINT_TOP_PRIORITY_RANK:
            continue
        updated = _item_last_activity(item)
        if updated is None or updated >= cutoff:
            continue
        idle_days = (now - updated).days
        label = _item_label(item, spec)
        out.append(_signal(
            "urgent_maintenance",
            "high",
            summary=f"Urgent maintenance: {label}",
            detail=(
                f"High-priority ticket on '{label}' is still '{item.get(status_field)}' "
                f"after {idle_days} days with no update (last activity {updated.date().isoformat()}). "
                f"Equipment downtime may need CEO-level escalation."
            ),
            related_id=item.get("id"),
            department_type=spec.get("type"),
            department_name=spec.get("name") or "Engineering & Maintenance",
            item_label=label,
            status=item.get(status_field),
            priority=item.get("priority"),
            idle_days=idle_days,
        ))
    return out


def detect_stalled_onboarding(
    items: list,
    spec: dict | None = None,
    *,
    threshold_days: int = STALLED_DEPARTMENT_DAYS,
    now: Optional[datetime] = None,
) -> list:
    """HR hires not yet `active` with no progress past `threshold_days`."""
    spec = spec or SPEC_BY_TYPE[TYPE_HR]
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=threshold_days)
    status_field = spec["status_field"]
    done_value = spec["done_value"]
    out = []
    for item in items or []:
        if item.get(status_field) == done_value:
            continue
        updated = _item_last_activity(item)
        if updated is None or updated >= cutoff:
            continue
        idle_days = (now - updated).days
        hire = _item_label(item, spec)
        out.append(_signal(
            "stalled_onboarding",
            "medium",
            summary=f"Onboarding for {hire} hasn't progressed in {idle_days} days",
            detail=(
                f"Onboarding for {hire} is still '{item.get(status_field)}' after {idle_days} days "
                f"with no update (last activity {updated.date().isoformat()})."
            ),
            related_id=item.get("id"),
            department_type=spec.get("type"),
            department_name=spec.get("name") or "HR",
            item_label=hire,
            status=item.get(status_field),
            idle_days=idle_days,
        ))
    return out



def detect_overdue_work_orders(work_orders: list, *, today: Optional[date] = None) -> list:
    """Flag work orders whose due_date has passed and status is not done.

    Straightforward date comparison only — no projection or estimation.
    """
    today = today or datetime.now(timezone.utc).date()
    out = []
    for wo in work_orders or []:
        if wo.get("status") == "done":
            continue
        due_d = parse_task_due_date(wo.get("due_date"))
        if due_d is None or due_d >= today:
            continue
        days_late = (today - due_d).days
        label = (wo.get("reference") or "").strip() or "Untitled work order"
        severity = "high" if days_late >= 7 else "medium"
        out.append(_signal(
            "overdue_work_order",
            severity,
            summary=f"Overdue work order: {label}",
            detail=(
                f"Work order '{label}' was due {due_d.isoformat()} "
                f"({days_late} day(s) late) and is still '{wo.get('status')}'."
            ),
            related_id=wo.get("id"),
            department_type="production",
            department_name="Production",
            item_label=label,
            due=due_d.isoformat(),
            days_late=days_late,
            status=wo.get("status"),
        ))
    return out


def compute_average_stage_time(progress_records: list) -> list:
    """Average exited_at - entered_at per stage for completed progress records.

    Stages with zero completed records are omitted — never a fabricated 0.
    """
    buckets: dict = {}
    for row in progress_records or []:
        stage_id = row.get("stage_id")
        if not stage_id:
            continue
        entered = _parse_iso_dt(row.get("entered_at"))
        exited = _parse_iso_dt(row.get("exited_at"))
        if entered is None or exited is None:
            continue
        if exited < entered:
            continue
        buckets.setdefault(stage_id, []).append((exited - entered).total_seconds())

    out = []
    for stage_id, durations in buckets.items():
        if not durations:
            continue
        avg = sum(durations) / len(durations)
        out.append({
            "stage_id": stage_id,
            "average_seconds": round(avg, 3),
            "sample_count": len(durations),
        })
    return out


def collect_department_signals(
    department_items: list | None,
    *,
    now: Optional[datetime] = None,
) -> list:
    """Run department stall detectors. `department_items` is [{spec, items}, ...] for enabled depts only."""
    now = now or datetime.now(timezone.utc)
    signals = []
    for bundle in department_items or []:
        spec = bundle.get("spec") or {}
        items = bundle.get("items") or []
        dtype = spec.get("type")
        if dtype == TYPE_HR:
            signals.extend(detect_stalled_onboarding(items, spec, now=now))
            continue
        if dtype == TYPE_PRODUCTION:
            signals.extend(detect_overdue_work_orders(items, today=now.date()))
        generic = detect_stalled_department_item(items, spec, now=now)
        if dtype == TYPE_ENGINEERING_MAINTENANCE:
            urgent = detect_urgent_maintenance(items, spec, now=now)
            urgent_ids = {s.get("related_id") for s in urgent}
            generic = [s for s in generic if s.get("related_id") not in urgent_ids]
            signals.extend(urgent)
        signals.extend(generic)
    return signals


def collect_signals(
    *,
    fin: dict,
    expense_by_month: dict,
    deals: list,
    tasks: list,
    updates: list,
    currency: str = "usd",
    department_items: list | None = None,
    now: Optional[datetime] = None,
) -> list:
    """Run all detectors and return a flat list of signals."""
    signals = []
    runway = detect_runway_risk(fin)
    if runway:
        signals.append(runway)
    signals.extend(detect_expense_spike(expense_by_month, currency=currency))
    signals.extend(detect_stalled_deals(deals, currency=currency, now=now))
    signals.extend(detect_overdue_tasks(tasks))
    signals.extend(detect_recurring_blockers(updates))
    signals.extend(collect_department_signals(department_items, now=now))
    # Cap volume so one regenerate can't spawn dozens of LLM calls
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: (severity_rank.get(s.get("severity"), 9), s.get("type") or ""))
    return signals[:SIGNAL_CAP]
