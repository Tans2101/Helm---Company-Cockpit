"""Proactive daily alerts + weekly digest cron runners and internal endpoints."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DB_NAME", "test_proactive_cron")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

import server


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _n):
        return list(self._rows)


def test_daily_alerts_endpoint_requires_cron_secret():
    with patch.object(server, "INTERNAL_CRON_SECRET", "cron-secret-test"):
        client = TestClient(server.app)
        assert client.post("/api/internal/run-daily-alerts").status_code == 401
        assert client.post(
            "/api/internal/run-daily-alerts",
            headers={"X-Trenston-Cron-Secret": "wrong"},
        ).status_code == 401


def test_daily_alerts_endpoint_runs_with_cron_header():
    with (
        patch.object(server, "INTERNAL_CRON_SECRET", "cron-secret-test"),
        patch.object(
            server,
            "run_daily_alerts_cron",
            new=AsyncMock(return_value={"workspaces_scanned": 0, "ok": 0, "skipped": 0, "errors": 0, "new_alerts": 0}),
        ),
    ):
        client = TestClient(server.app)
        res = client.post(
            "/api/internal/run-daily-alerts",
            headers={"X-Trenston-Cron-Secret": "cron-secret-test"},
        )
    assert res.status_code == 200
    assert res.json()["workspaces_scanned"] == 0


def test_weekly_digest_endpoint_requires_cron_secret():
    with patch.object(server, "INTERNAL_CRON_SECRET", "cron-secret-test"):
        client = TestClient(server.app)
        assert client.post("/api/internal/run-weekly-digest").status_code == 401
        assert client.post(
            "/api/internal/run-weekly-digest",
            headers={"X-Trenston-Cron-Secret": "wrong"},
        ).status_code == 401


def test_weekly_digest_endpoint_runs_with_cron_header():
    with (
        patch.object(server, "INTERNAL_CRON_SECRET", "cron-secret-test"),
        patch.object(
            server,
            "run_weekly_digest_cron",
            new=AsyncMock(return_value={"workspaces_scanned": 0, "sent": 0, "week": "2026-W38"}),
        ),
    ):
        client = TestClient(server.app)
        res = client.post(
            "/api/internal/run-weekly-digest",
            headers={"X-Trenston-Cron-Secret": "cron-secret-test"},
        )
    assert res.status_code == 200
    assert res.json()["sent"] == 0


def test_run_daily_alerts_isolates_workspace_failures():
    rows = [
        {"workspace_id": "ws_ok", "name": "Ok Co"},
        {"workspace_id": "ws_bad", "name": "Bad Co"},
        {"workspace_id": "ws_skip", "name": "Skip Co"},
    ]
    fake_db = MagicMock()
    fake_db.workspaces.find = MagicMock(return_value=_Cursor(rows))

    async def fake_generate(wid, *, raise_on_rate_limit=False):
        assert raise_on_rate_limit is False
        if wid == "ws_bad":
            raise RuntimeError("boom")
        if wid == "ws_skip":
            return {"skipped": "rate_limited"}
        return {
            "ok": True,
            "notifications": {"new_alerts": 2, "emailed": True, "slack": False},
        }

    with (
        patch.object(server, "db", fake_db),
        patch.object(server, "_generate_insights", side_effect=fake_generate),
    ):
        stats = asyncio.run(server.run_daily_alerts_cron())

    assert stats["workspaces_scanned"] == 3
    assert stats["ok"] == 1
    assert stats["skipped"] == 1
    assert stats["errors"] == 1
    assert stats["new_alerts"] == 2


def test_run_weekly_digest_emails_pdf_and_debounces():
    week = server._iso_week_key(datetime(2026, 9, 17, tzinfo=timezone.utc))
    rows = [
        {
            "workspace_id": "ws_send",
            "name": "Send Co",
            "plan": "growth",
        },
        {
            "workspace_id": "ws_done",
            "name": "Done Co",
            "plan": "growth",
            "weekly_digest_emailed_week": week,
        },
        {
            "workspace_id": "ws_free",
            "name": "Free Co",
            "plan": "free",
        },
    ]
    fake_db = MagicMock()
    fake_db.workspaces.find = MagicMock(return_value=_Cursor(rows))
    fake_db.workspaces.update_one = AsyncMock()
    fake_db.email_suppressions.find_one = AsyncMock(return_value=None)

    sent = []

    async def fake_send(*, to, subject, html, attachments=None, headers=None):
        sent.append({
            "to": to,
            "subject": subject,
            "html": html,
            "attachments": attachments,
            "headers": headers,
        })
        return {"sent": True, "id": "email_1"}

    async def fake_recipients(wid):
        return ["ceo@send.test"] if wid == "ws_send" else []

    with (
        patch.object(server, "db", fake_db),
        patch.object(server, "BILLING_ENFORCED", True),
        patch.object(server, "SESSION_SECRET", "weekly-digest-test-secret"),
        patch.object(server, "_alert_recipient_emails", side_effect=fake_recipients),
        patch.object(
            server,
            "_generate_weekly_pack_content",
            new=AsyncMock(return_value={
                "content": "# Send Co: this week\n\nQuiet week.",
                "workspace_name": "Send Co",
                "workspace_id": "ws_send",
            }),
        ),
        patch.object(server, "send_resend_email", side_effect=fake_send),
        patch(
            "weekly_pack_export.render_weekly_pack_pdf",
            return_value=b"%PDF-1.4 fake",
        ),
        patch(
            "weekly_pack_export.pdf_filename",
            return_value="Trenston-Weekly-Pack-Send-Co-2026-09-17.pdf",
        ),
        patch.object(server, "_iso_week_key", return_value=week),
    ):
        stats = asyncio.run(server.run_weekly_digest_cron())

    assert stats["sent"] == 1
    assert stats["skipped_already"] == 1
    assert stats["skipped_plan"] == 1
    assert stats["errors"] == 0
    assert len(sent) == 1
    assert sent[0]["to"] == ["ceo@send.test"]
    assert "Send Co" in sent[0]["subject"]
    assert "Unsubscribe" in sent[0]["html"]
    assert "BGC, Taguig, Philippines" in sent[0]["html"]
    assert sent[0]["headers"] and "List-Unsubscribe" in sent[0]["headers"]
    assert sent[0]["attachments"][0]["filename"].endswith(".pdf")
    assert sent[0]["attachments"][0]["content"] == b"%PDF-1.4 fake"
    fake_db.workspaces.update_one.assert_awaited_once()
    set_fields = fake_db.workspaces.update_one.await_args.args[1]["$set"]
    assert set_fields["weekly_digest_emailed_week"] == week


def test_run_weekly_digest_continues_after_one_failure():
    rows = [
        {"workspace_id": "ws_bad", "name": "Bad", "plan": "growth"},
        {"workspace_id": "ws_ok", "name": "Ok", "plan": "growth"},
    ]
    fake_db = MagicMock()
    fake_db.workspaces.find = MagicMock(return_value=_Cursor(rows))
    fake_db.workspaces.update_one = AsyncMock()
    fake_db.email_suppressions.find_one = AsyncMock(return_value=None)

    async def fake_pack(wid):
        if wid == "ws_bad":
            raise RuntimeError("llm down")
        return {
            "content": "# Ok: this week\n\nFine.",
            "workspace_name": "Ok",
            "workspace_id": wid,
        }

    with (
        patch.object(server, "db", fake_db),
        patch.object(server, "BILLING_ENFORCED", True),
        patch.object(server, "SESSION_SECRET", "weekly-digest-test-secret"),
        patch.object(server, "_alert_recipient_emails", new=AsyncMock(return_value=["a@b.test"])),
        patch.object(server, "_generate_weekly_pack_content", side_effect=fake_pack),
        patch.object(server, "send_resend_email", new=AsyncMock(return_value={"sent": True})),
        patch("weekly_pack_export.render_weekly_pack_pdf", return_value=b"%PDF"),
        patch("weekly_pack_export.pdf_filename", return_value="pack.pdf"),
        patch.object(server, "_iso_week_key", return_value="2026-W38"),
    ):
        stats = asyncio.run(server.run_weekly_digest_cron())

    assert stats["errors"] == 1
    assert stats["sent"] == 1


@pytest.mark.asyncio
async def test_weekly_pack_endpoint_uses_shared_helper():
    principal = {"workspace_id": "ws_1", "user_id": "u1", "pack": "owner"}
    with patch.object(
        server,
        "_generate_weekly_pack_content",
        new=AsyncMock(return_value={"content": "shared body", "workspace_name": "Acme"}),
    ) as helper:
        result = await server.weekly_pack(principal=principal)
    assert result == {"content": "shared body"}
    helper.assert_awaited_once_with("ws_1")


def test_iso_week_key_format():
    key = server._iso_week_key(datetime(2026, 9, 17, tzinfo=timezone.utc))
    assert key == "2026-W38"
