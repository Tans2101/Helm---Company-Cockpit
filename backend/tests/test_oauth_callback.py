"""Google OAuth callback must never 500 after the user clicks Allow."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_oauth_callback")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-secret")
os.environ.setdefault("APP_URL", "https://www.helmcontrol.online")

import server  # noqa: E402


def test_oauth_datetime_expired_accepts_naive_mongo_datetimes():
    naive = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=8)
    assert naive.tzinfo is None
    assert server._oauth_datetime_expired(naive) is False
    past = datetime(2020, 1, 1, 12, 0, 0)
    assert server._oauth_datetime_expired(past) is True
    aware = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert server._oauth_datetime_expired(aware) is False
    assert server._oauth_datetime_expired("not-a-date") is True


def test_sanitize_oauth_token_payload_drops_id_token_and_joins_scope():
    cleaned = server.sanitize_oauth_token_payload({
        "access_token": "ya29.abc",
        "refresh_token": "1//xyz",
        "expires_in": 3599,
        "token_type": "Bearer",
        "scope": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
        ],
        "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.huge",
        "nested": {"oops": object()},
    })
    assert "id_token" not in cleaned
    assert "nested" not in cleaned
    assert cleaned["access_token"] == "ya29.abc"
    assert "gmail.compose" in cleaned["scope"]
    # Must be JSON-serializable for Fernet seal
    import json
    json.dumps(cleaned)


def test_google_callback_succeeds_with_naive_state_expiry():
    state = server._sign_state("google", "ws_oauth", "user_oauth", "nonce1")
    mock_db = MagicMock()
    mock_db.oauth_states.find_one_and_delete = AsyncMock(return_value={
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=9),
    })
    mock_db.memberships.find_one = AsyncMock(return_value={
        "workspace_id": "ws_oauth",
        "user_id": "user_oauth",
        "status": "active",
        "pack": "owner",
        "role": "owner",
    })
    mock_db.workspaces.update_one = AsyncMock(return_value=None)

    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {
        "access_token": "ya29.live",
        "refresh_token": "1//refresh",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/calendar.events",
        "id_token": "drop-me",
    }
    token_resp.text = "{}"
    mock_hc = AsyncMock()
    mock_hc.post = AsyncMock(return_value=token_resp)
    mock_hc.__aenter__ = AsyncMock(return_value=mock_hc)
    mock_hc.__aexit__ = AsyncMock(return_value=None)

    with patch.object(server, "db", mock_db), patch("httpx.AsyncClient", return_value=mock_hc), patch.object(
        server, "_store_integration_tokens", new_callable=AsyncMock,
    ) as store:
        client = TestClient(server.app)
        r = client.get(
            "/api/oauth/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert r.status_code in (302, 307)
    assert "connected=google" in r.headers.get("location", "")
    stored = store.await_args.args[2]
    assert stored["access_token"] == "ya29.live"
    assert "id_token" not in stored


def test_google_callback_never_500s_on_unexpected_error():
    state = server._sign_state("google", "ws_oauth", "user_oauth", "nonce2")
    mock_db = MagicMock()
    mock_db.oauth_states.find_one_and_delete = AsyncMock(side_effect=RuntimeError("mongo blip"))

    with patch.object(server, "db", mock_db):
        client = TestClient(server.app)
        r = client.get(
            "/api/oauth/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert r.status_code in (302, 307)
    assert "error=token" in r.headers.get("location", "")
    assert r.status_code != 500
