"""Security helpers and production guardrails."""
import asyncio
import io
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

# Ensure server module can import (needs Mongo env at import time).
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_security")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import _allowed_auth_redirect, _read_validated_document  # noqa: E402


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
    from cryptography.fernet import Fernet

    monkeypatch.setattr(server, "ENVIRONMENT", "production")
    monkeypatch.setattr(server, "SESSION_SECRET", "change-me-in-production")
    monkeypatch.setattr(server, "CORS_ORIGINS", [])
    monkeypatch.setattr(server, "ALLOW_DEMO_LOGIN", True)
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
    with pytest.raises(RuntimeError) as exc:
        server._enforce_production_config()
    msg = str(exc.value)
    assert "SESSION_SECRET" in msg
    assert "OAUTH_STATE_SECRET" in msg
    assert "CORS_ORIGINS" in msg
    assert "ALLOW_DEMO_LOGIN" in msg


def test_production_requires_integration_encryption_key(monkeypatch):
    import server

    monkeypatch.setattr(server, "ENVIRONMENT", "production")
    monkeypatch.delenv("INTEGRATION_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        server._enforce_production_config()
    assert "INTEGRATION_ENCRYPTION_KEY" in str(exc.value)


def test_production_rejects_invalid_integration_encryption_key(monkeypatch):
    import server

    monkeypatch.setattr(server, "ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", "not-a-fernet-key")
    with pytest.raises(RuntimeError) as exc:
        server._enforce_production_config()
    assert "valid Fernet key" in str(exc.value)


def test_google_scopes_include_gmail():
    import server

    assert "https://www.googleapis.com/auth/gmail.readonly" in server.GOOGLE_SCOPES
    assert "https://www.googleapis.com/auth/calendar.readonly" in server.GOOGLE_SCOPES


def _upload(data: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        filename="document",
        headers=Headers({"content-type": content_type}),
    )


def test_document_upload_validates_magic_bytes():
    pdf = _upload(b"%PDF-1.7\nsafe", "application/pdf")
    assert asyncio.run(_read_validated_document(pdf)).startswith(b"%PDF-")

    disguised = _upload(b"<script>alert(1)</script>", "application/pdf")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_read_validated_document(disguised))
    assert exc.value.status_code == 400
    assert "declared type" in exc.value.detail


def test_document_upload_stops_at_size_limit():
    import server

    oversized = _upload(b"%PDF-" + b"x" * server.MAX_DOC_BYTES, "application/pdf")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_read_validated_document(oversized))
    assert exc.value.status_code == 400
    assert "15MB" in exc.value.detail
