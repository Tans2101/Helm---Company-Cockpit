"""Security helpers and production guardrails."""
import os
import sys
from pathlib import Path

import pytest

# Ensure server module can import (needs Mongo env at import time).
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_security")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import _allowed_auth_redirect  # noqa: E402


@pytest.mark.parametrize(
    "url,app_url,origins,expected",
    [
        ("/app", "https://helm.vercel.app", [], True),
        ("https://helm.vercel.app/app", "https://helm.vercel.app", [], True),
        ("https://evil.com/phish", "https://helm.vercel.app", [], False),
        ("//evil.com", "https://helm.vercel.app", [], False),
        ("https://preview.vercel.app/login", "", ["https://preview.vercel.app"], True),
    ],
)
def test_allowed_auth_redirect(monkeypatch, url, app_url, origins, expected):
    import server

    monkeypatch.setattr(server, "APP_URL", app_url)
    monkeypatch.setattr(server, "CORS_ORIGINS", origins)
    assert _allowed_auth_redirect(url) is expected


def test_cors_regex_not_wildcard_dot_star():
    import server

    assert server._cors_regex != ".*"
    assert server._cors_regex != r".*"


def test_production_config_allows_development():
    import server

    server._enforce_production_config()


def test_production_config_refuses_insecure(monkeypatch):
    import server

    monkeypatch.setattr(server, "ENVIRONMENT", "production")
    monkeypatch.setattr(server, "SESSION_SECRET", "change-me-in-production")
    monkeypatch.setattr(server, "CORS_ORIGINS", [])
    monkeypatch.setattr(server, "ALLOW_DEMO_LOGIN", True)
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
    with pytest.raises(RuntimeError) as exc:
        server._enforce_production_config()
    msg = str(exc.value)
    assert "SESSION_SECRET" in msg
    assert "OAUTH_STATE_SECRET" in msg
    assert "CORS_ORIGINS" in msg
    assert "ALLOW_DEMO_LOGIN" in msg


def test_google_scopes_exclude_gmail():
    import server

    assert "https://www.googleapis.com/auth/gmail.readonly" not in server.GOOGLE_SCOPES
    assert "https://www.googleapis.com/auth/calendar.readonly" in server.GOOGLE_SCOPES
