"""Pure signal detectors for CEO decision / delegate suggestions.

Each detector takes already-fetched workspace data and returns structured
signals the LLM can draft into decision or delegate cards.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Optional


SEVERITIES = ("high", "medium", "low")
STALLED_DEAL_DAYS = 14
RUNWAY_MONTHS_THRESHOLD = 6
BURN_INCREASE_PCT = 0.20
EXPENSE_SPIKE_PCT = 0.25

# Signals that become decision suggestions vs delegate suggestions
DECISION_SIGNAL_TYPES = frozenset({
    "runway_risk",
    "burn_increase",
    "expense_spike",
    "stalled_deal",
})
DELEGATE_SIGNAL_TYPES = frozenset({
    "overdue_task",
    "recurring_blocker",
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

    Recurring expenses are expanded through the current/latest month horizon
    (monthly = full amount each month; annual = amount/12 each month).
    """
    import finance_recurrence as fin_recur

    by_month: dict = {}
    horizon = fin_recur.resolve_expense_horizon(entries or [])
    for e in entries or []:
        if e.get("type") != "expense":
            continue
        cat = (e.get("category") or "Other").strip() or "Other"
        for month, amt in fin_recur.iter_expense_month_amounts(e, horizon):
            by_month.setdefault(month, {})
            by_month[month][cat] = by_month[month].get(cat, 0.0) + float(amt)
    return by_month


def detect_runway_risk(fin: dict) -> Optional[dict]:
    """Fire if runway < 6 months, or burn rose materially month over month."""
    if not fin or not fin.get("has_data"):
        return None
    runway = fin.get("runway_months")
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


def detect_expense_spike(expense_by_month: dict) -> list:
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
                f"{cat}: ${prev_amt:,.0f} in {prev_m} → ${curr_amt:,.0f} in {curr_m} "
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


def detect_stalled_deals(deals: list, *, now: Optional[datetime] = None, days: int = STALLED_DEAL_DAYS) -> list:
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
        value_s = f"${float(value):,.0f}" if value is not None else "unknown value"
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


def collect_signals(
    *,
    fin: dict,
    expense_by_month: dict,
    deals: list,
    tasks: list,
    updates: list,
) -> list:
    """Run all detectors and return a flat list of signals."""
    signals = []
    runway = detect_runway_risk(fin)
    if runway:
        signals.append(runway)
    signals.extend(detect_expense_spike(expense_by_month))
    signals.extend(detect_stalled_deals(deals))
    signals.extend(detect_overdue_tasks(tasks))
    signals.extend(detect_recurring_blockers(updates))
    # Cap volume so one regenerate can't spawn dozens of LLM calls
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: (severity_rank.get(s.get("severity"), 9), s.get("type") or ""))
    return signals[:8]
