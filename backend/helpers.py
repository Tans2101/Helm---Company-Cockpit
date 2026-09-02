"""Shared helpers: activity log, financials, email."""
import asyncio
import html
import logging
import uuid
from datetime import datetime, timezone

import resend
from db import RESEND_API_KEY, SENDER_EMAIL, db

logger = logging.getLogger("helm")

def _invite_email_html(inviter_name: str, workspace_name: str, role: str, app_url: str) -> str:
    inviter_name = html.escape(inviter_name)
    workspace_name = html.escape(workspace_name)
    role = html.escape(role)
    app_url = html.escape(app_url, quote=True)
    return f"""\
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#09090b;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#09090b;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#121214;border:1px solid rgba(255,255,255,0.08);border-radius:14px;overflow:hidden;">
<tr><td style="padding:32px 36px 8px 36px;">
<table cellpadding="0" cellspacing="0"><tr>
<td style="width:34px;height:34px;background:rgba(201,169,98,0.15);border:1px solid rgba(201,169,98,0.35);border-radius:8px;text-align:center;vertical-align:middle;color:#c9a962;font-weight:600;font-size:15px;">H</td>
<td style="padding-left:10px;color:#ffffff;font-size:16px;font-weight:600;">Helm</td>
</tr></table>
<p style="color:#c9a962;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:22px 0 0 0;">You've been added</p>
<h1 style="color:#ffffff;font-size:24px;font-weight:400;margin:10px 0 0 0;line-height:1.3;">{inviter_name} invited you to<br><span style="color:#c9a962;">{workspace_name}</span></h1>
<p style="color:#a1a1aa;font-size:15px;line-height:1.6;margin:18px 0 0 0;">You now have <b style="color:#ffffff;">{role}</b> access to this company's command center on Helm — the CEO Operating System. Sign in with Google to see the morning briefing, decisions, financials and more.</p>
<table cellpadding="0" cellspacing="0" style="margin:28px 0 8px 0;"><tr>
<td style="background:#c9a962;border-radius:8px;">
<a href="{app_url}" style="display:inline-block;padding:12px 26px;color:#09090b;font-size:14px;font-weight:600;text-decoration:none;">Open Helm &rarr;</a>
</td></tr></table>
</td></tr>
<tr><td style="padding:20px 36px 30px 36px;border-top:1px solid rgba(255,255,255,0.06);">
<p style="color:#52525b;font-size:12px;margin:0;line-height:1.6;">Know what matters before your first meeting.<br>If you didn't expect this invite, you can ignore this email.</p>
</td></tr>
</table>
</td></tr></table></body></html>"""


async def send_invite_email(to_email: str, inviter_name: str, workspace_name: str, role: str, app_url: str):
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping invite email to %s", to_email)
        return {"sent": False, "reason": "no_key"}
    resend.api_key = RESEND_API_KEY
    params = {
        "from": SENDER_EMAIL, "to": [to_email],
        "subject": f"{inviter_name} invited you to {workspace_name} on Helm",
        "html": _invite_email_html(inviter_name, workspace_name, role, app_url),
    }
    try:
        email = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "id": (email or {}).get("id")}
    except Exception:
        logger.exception("resend send failed")
        return {"sent": False, "reason": "error"}

def rel_time(iso: str) -> str:
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except Exception:
        return ""
    secs = (datetime.now(timezone.utc) - t).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


async def log_activity(principal, module, action, summary, patch=None):
    doc = {
        "activity_id": f"act_{uuid.uuid4().hex[:12]}",
        "workspace_id": principal["workspace_id"],
        "actor_user_id": principal["user_id"],
        "actor_name": principal.get("name") or principal.get("email") or "Someone",
        "module": module, "action": action, "summary": summary,
        "patch": patch or {}, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.activities.insert_one(doc)
    return doc


# ------------------------- Financials (computed from entries) -------------------------
def fmt_money(n):
    n = float(n or 0)
    neg = n < 0
    a = abs(n)
    if a >= 1_000_000:
        s = f"${a/1_000_000:.2f}M"
    elif a >= 1_000:
        s = f"${a/1_000:.0f}K"
    else:
        s = f"${a:,.0f}"
    return f"-{s}" if neg else s


async def compute_financials(workspace_id: str):
    from collections import defaultdict
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0, "financial_settings": 1})
    settings = (ws or {}).get("financial_settings") or {"cash": 0, "gross_margin": None, "currency": "usd"}
    entries = await db.financial_entries.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(5000)
    rev_by, exp_by, rec_by = defaultdict(float), defaultdict(float), defaultdict(float)
    exp_cat = defaultdict(float)
    for e in entries:
        if e["type"] == "revenue":
            rev_by[e["month"]] += e["amount"]
            if e.get("recurring"):
                rec_by[e["month"]] += e["amount"]
        else:
            exp_by[e["month"]] += e["amount"]
            exp_cat[e.get("category") or "Other"] += e["amount"]
    months = sorted(set(list(rev_by) + list(exp_by)))
    last = months[-6:]

    def lbl(m):
        return datetime.strptime(m, "%Y-%m").strftime("%b")

    revenue_series = [{"month": lbl(m), "revenue": round(rev_by[m]), "expenses": round(exp_by[m])} for m in last]
    burn_series = [{"month": lbl(m), "burn": round(exp_by[m] - rev_by[m])} for m in last]
    latest = months[-1] if months else None
    mrr_val = (rec_by[latest] if latest and rec_by[latest] > 0 else (rev_by[latest] if latest else 0))
    cash = settings.get("cash") or 0
    net = [max(exp_by[m] - rev_by[m], 0) for m in months[-3:]]
    avg_burn = sum(net) / len(net) if net else 0
    runway = round(cash / avg_burn, 1) if avg_burn > 0 else None
    burn_val = (exp_by[latest] - rev_by[latest]) if latest else 0
    total_exp = sum(exp_cat.values())
    expense_breakdown = ([{"name": k, "value": round(v / total_exp * 100)} for k, v in sorted(exp_cat.items(), key=lambda x: -x[1])] if total_exp else [])
    gm = settings.get("gross_margin")
    scenarios = []
    if runway:
        scenarios = [
            {"name": "Base", "runway": runway, "desc": "Current net burn held."},
            {"name": "Efficient", "runway": round(cash / (avg_burn * 0.8), 1), "desc": "Trim burn 20%."},
            {"name": "Aggressive Hire", "runway": round(cash / (avg_burn * 1.4), 1), "desc": "Scale spend 40%."},
        ]
    mrr_delta = 0
    if len(revenue_series) >= 2 and revenue_series[-2]["revenue"] > 0:
        mrr_delta = round((revenue_series[-1]["revenue"] - revenue_series[-2]["revenue"]) / revenue_series[-2]["revenue"] * 100, 1)
    return {
        "mrr": fmt_money(mrr_val), "arr": fmt_money(mrr_val * 12), "runway_months": runway,
        "burn": fmt_money(burn_val), "cash": fmt_money(cash),
        "gross_margin": ((f"{int(gm)}%" if float(gm).is_integer() else f"{gm}%") if gm is not None else "—"),
        "revenue_series": revenue_series, "burn_series": burn_series, "scenarios": scenarios,
        "expense_breakdown": expense_breakdown, "settings": settings,
        "mrr_delta": mrr_delta, "spark": [r["revenue"] for r in revenue_series],
        "burn_tone": "negative" if burn_val > 0 else "positive", "has_data": bool(entries),
    }
