"""Clerk instance sync for Vercel deployment."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_clerk_sync")
os.environ["CLERK_SECRET_KEY"] = "sk_live_test"
os.environ["CLERK_JWKS_URL"] = "https://causal-caribou-2352.clerk.accounts.dev/.well-known/jwks.json"
os.environ["FRONTEND_URL"] = "https://helm-company-cockpit.vercel.app"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import clerk_auth  # noqa: E402


def test_helm_frontend_origins_includes_vercel():
    origins = clerk_auth.helm_frontend_origins()
    assert "https://helm-company-cockpit.vercel.app" in origins
    assert "http://localhost:3000" in origins


def test_primary_frontend_origin_prefers_https():
    assert clerk_auth.primary_frontend_origin() == "https://helm-company-cockpit.vercel.app"


def test_sync_clerk_instance_patches_dev_origin():
    instance_before = {
        "environment_type": "development",
        "allowed_origins": ["http://localhost:3000"],
    }
    instance_after = {
        "environment_type": "development",
        "allowed_origins": [
            "http://localhost:3000",
            "https://helm-company-cockpit.vercel.app",
        ],
    }

    class Resp:
        def __init__(self, data, status=200, text=""):
            self.status_code = status
            self._data = data
            self.text = text

        def json(self):
            return self._data

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[
        Resp(instance_before),
        Resp(instance_after),
    ])
    mock_client.patch = AsyncMock(return_value=Resp({}, 204))

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None

    with patch("clerk_auth.httpx.AsyncClient", return_value=mock_cm):
        result = asyncio.run(clerk_auth.sync_clerk_instance())

    assert result["synced"] is True
    assert result["environment_type"] == "development"
    mock_client.patch.assert_called_once()
    body = mock_client.patch.call_args.kwargs["json"]
    assert body["development_origin"] == "https://helm-company-cockpit.vercel.app"
    assert "https://helm-company-cockpit.vercel.app" in body["allowed_origins"]
    assert body["url_based_session_syncing"] is True


def test_sync_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(clerk_auth, "CLERK_SECRET_KEY", "")
    result = asyncio.run(clerk_auth.sync_clerk_instance())
    assert result["synced"] is False
    assert result["reason"] == "clerk_not_configured"
