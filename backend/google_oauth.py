"""Google OAuth — token refresh and Calendar API helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


class GoogleAuthError(Exception):
    """Refresh token invalid or revoked — user must reconnect."""


def _token_needs_refresh(tokens: dict) -> bool:
    obtained = tokens.get("obtained_at")
    if not obtained:
        return True
    try:
        obtained_dt = datetime.fromisoformat(obtained.replace("Z", "+00:00"))
    except ValueError:
        return True
    expires_in = int(tokens.get("expires_in", 3600))
    return obtained_dt + timedelta(seconds=max(expires_in - 300, 0)) <= datetime.now(timezone.utc)


async def refresh_google_token(tokens: dict, client_id: str, client_secret: str) -> dict:
    """Return valid tokens, refreshing via Google when the access token is near expiry."""
    if not _token_needs_refresh(tokens):
        return tokens
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise GoogleAuthError("Missing refresh token — reconnect Google Calendar")
    if not client_id or not client_secret:
        raise GoogleAuthError("Google OAuth is not configured")

    async with httpx.AsyncClient(timeout=30.0) as hc:
        resp = await hc.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise GoogleAuthError(resp.text[:300] or "Token refresh failed")

    updated = {**tokens, **resp.json()}
    updated["obtained_at"] = datetime.now(timezone.utc).isoformat()
    if "refresh_token" not in updated and refresh_token:
        updated["refresh_token"] = refresh_token
    return updated


def _parse_event_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    if len(value) == 10:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _infer_meeting_type(title: str, attendee_count: int) -> str:
    lower = (title or "").lower()
    if attendee_count <= 2 or "1:1" in lower or "1-1" in lower:
        return "1:1"
    if any(k in lower for k in ("board", "investor", "advisor")):
        return "Board"
    if any(k in lower for k in ("demo", "sales", "customer", "prospect", "acme")):
        return "Sales"
    return "Internal"


def _map_google_event(event: dict) -> Optional[dict]:
    start_obj = event.get("start") or {}
    end_obj = event.get("end") or {}
    start_raw = start_obj.get("dateTime") or start_obj.get("date")
    end_raw = end_obj.get("dateTime") or end_obj.get("date")
    all_day = bool(start_obj.get("date") and not start_obj.get("dateTime"))
    start_dt = _parse_event_dt(start_raw or "")
    end_dt = _parse_event_dt(end_raw or "")
    if not start_dt:
        return None

    if end_dt:
        duration_m = max(int((end_dt - start_dt).total_seconds() // 60), 15)
    else:
        duration_m = 60

    attendees = event.get("attendees") or []
    attendee_count = len(attendees) if attendees else 1
    title = event.get("summary") or "Untitled meeting"

    return {
        "id": event.get("id") or f"gcal_{hash(title) & 0xfffffff}",
        "title": title,
        "time": start_dt.strftime("%H:%M"),
        "duration": duration_m,
        "attendees": attendee_count,
        "type": _infer_meeting_type(title, attendee_count),
        "prep": None,
        "importance": "medium",
        "source": "google_calendar",
        "date": start_dt.strftime("%Y-%m-%d"),
        "start_at": start_dt.isoformat(),
        "end_at": end_dt.isoformat() if end_dt else None,
        "all_day": all_day,
    }


def _today_bounds() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def week_bounds(week_start: datetime) -> tuple[str, str]:
    """Return ISO bounds for a 7-day window starting at week_start (UTC midnight)."""
    start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


async def _fetch_calendar_events(
    tokens: dict,
    client_id: str,
    client_secret: str,
    time_min: str,
    time_max: str,
    *,
    max_results: int = 100,
) -> tuple[list[dict], dict]:
    tokens = await refresh_google_token(tokens, client_id, client_secret)
    access_token = tokens.get("access_token")
    if not access_token:
        raise GoogleAuthError("Missing access token")

    async with httpx.AsyncClient(timeout=45.0) as hc:
        resp = await hc.get(
            CALENDAR_EVENTS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            },
        )
    if resp.status_code == 401:
        raise GoogleAuthError("Google access token rejected — reconnect Google Calendar")
    if resp.status_code != 200:
        raise RuntimeError(f"Google Calendar API failed ({resp.status_code}): {resp.text[:300]}")

    items = resp.json().get("items") or []
    events = [m for m in (_map_google_event(ev) for ev in items) if m]
    return events, tokens


def _compute_hours(meetings: list[dict]) -> tuple[float, float]:
    meeting_m = sum(m.get("duration", 0) for m in meetings)
    meeting_hours = round(meeting_m / 60, 2)
    focus_hours = round(max(8 - meeting_hours, 0), 2)
    return focus_hours, meeting_hours


async def fetch_today_calendar(
    tokens: dict,
    client_id: str,
    client_secret: str,
    *,
    max_results: int = 25,
) -> tuple[list[dict], float, float, dict]:
    """Fetch today's primary-calendar events. Returns (meetings, focus_hours, meeting_hours, tokens)."""
    time_min, time_max = _today_bounds()
    meetings, tokens = await _fetch_calendar_events(
        tokens, client_id, client_secret, time_min, time_max, max_results=max_results,
    )
    focus_hours, meeting_hours = _compute_hours(meetings)
    return meetings, focus_hours, meeting_hours, tokens


async def fetch_week_calendar(
    tokens: dict,
    client_id: str,
    client_secret: str,
    week_start: datetime,
    *,
    max_results: int = 100,
) -> tuple[list[dict], dict]:
    """Fetch one week of events from primary calendar."""
    time_min, time_max = week_bounds(week_start)
    return await _fetch_calendar_events(
        tokens, client_id, client_secret, time_min, time_max, max_results=max_results,
    )
