"""Clerk instance sync for helmcontrol.online deployment."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_clerk_sync")
os.environ["CLERK_SECRET_KEY"] = "sk_live_test"
os.environ["CLERK_JWKS_URL"] = "https://clerk.apexcoach.tech/.well-known/jwks.json"
os.environ["FRONTEND_URL"] = "https://helmcontrol.online"
os.environ["APP_URL"] = "https://helmcontrol.online"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import clerk_auth  # noqa: E402


def test_helm_frontend_origins_includes_helmcontrol():
    origins = clerk_auth.helm_frontend_origins()
    assert "https://helmcontrol.online" in origins
    assert "http://localhost:3000" in origins


def test_primary_frontend_origin_prefers_helmcontrol():
    assert clerk_auth.primary_frontend_origin() == "https://helmcontrol.online"


def test_sync_clerk_instance_patches_dev_origin():
    instance_before = {
        "environment_type": "development",
        "allowed_origins": ["http://localhost:3000"],
    }
    instance_after = {
        "environment_type": "development",
        "allowed_origins": sorted(clerk_auth.helm_frontend_origins()),
    }

    class Resp:
        def __init__(self, data, status=200, text=""):
            self.status_code = status
            self._data = data
            self.text = text

        def json(self):
            return self._data

    portal_resp = Resp({"after_sign_in_url": "", "after_sign_up_url": ""})
    domains_resp = Resp({"data": [{"name": "helmcontrol.online", "id": "dom_1"}]})
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[
        Resp(instance_before),
        Resp(instance_after),
        portal_resp,
        domains_resp,
    ])
    mock_client.patch = AsyncMock(return_value=Resp({}, 204))
    mock_client.post = AsyncMock(return_value=Resp({}, 201))

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None

    with patch("clerk_auth.httpx.AsyncClient", return_value=mock_cm):
        result = asyncio.run(clerk_auth.sync_clerk_instance())

    assert result["synced"] is True
    assert result["environment_type"] == "development"
    assert mock_client.patch.call_count >= 1
    body = mock_client.patch.call_args_list[0].kwargs["json"]
    assert body["development_origin"] == "https://helmcontrol.online"
    assert "https://helmcontrol.online" in body["allowed_origins"]
    assert body["url_based_session_syncing"] is True


def test_sync_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(clerk_auth, "CLERK_SECRET_KEY", "")
    result = asyncio.run(clerk_auth.sync_clerk_instance())
    assert result["synced"] is False
    assert result["reason"] == "clerk_not_configured"
