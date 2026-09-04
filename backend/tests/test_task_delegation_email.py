"""Task delegation email notifications."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_task_delegation_email")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


@pytest.mark.asyncio
async def test_notify_sends_only_when_assignee_changes():
    principal = {
        "user_id": "u_ceo",
        "name": "CEO",
        "email": "ceo@acme.com",
        "workspace_id": "ws_1",
    }
    task = {"id": "t_1", "title": "Ship invoices", "note": "Due Friday"}
    sent = []

    async def fake_notify(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return {"sent": True}

    mock_db = MagicMock()
    mock_db.users.find_one = AsyncMock(return_value={"email": "alex@acme.com", "name": "Alex"})
    mock_db.memberships.find_one = AsyncMock(return_value=None)

    with patch.object(server, "db", mock_db), \
         patch.object(server, "send_notification_email", new=fake_notify), \
         patch.object(server, "APP_URL", "https://www.helmcontrol.online"), \
         patch.object(server, "FRONTEND_URL", "https://www.helmcontrol.online"):
        # No change
        r0 = await server.notify_task_delegated(
            assignee_user_id="u_alex",
            previous_assignee_user_id="u_alex",
            task=task,
            principal=principal,
            workspace_name="Acme",
        )
        assert r0["reason"] == "unchanged"
        assert sent == []

        # First assign
        r1 = await server.notify_task_delegated(
            assignee_user_id="u_alex",
            previous_assignee_user_id=None,
            task=task,
            principal=principal,
            workspace_name="Acme",
        )
        assert r1["sent"] is True
        assert len(sent) == 1
        assert sent[0]["to"] == "alex@acme.com"
        assert "Ship invoices" in sent[0]["subject"]
        assert "/app/tasks?task=t_1" in sent[0]["body"]

        # Reassign to other
        mock_db.users.find_one = AsyncMock(return_value={"email": "sam@acme.com", "name": "Sam"})
        r2 = await server.notify_task_delegated(
            assignee_user_id="u_sam",
            previous_assignee_user_id="u_alex",
            task=task,
            principal=principal,
            workspace_name="Acme",
        )
        assert r2["sent"] is True
        assert len(sent) == 2
        assert sent[1]["to"] == "sam@acme.com"


@pytest.mark.asyncio
async def test_notify_skips_self_assign_and_survives_send_failure():
    principal = {"user_id": "u_ceo", "name": "CEO", "email": "ceo@acme.com", "workspace_id": "ws_1"}
    task = {"id": "t_2", "title": "Self"}

    r = await server.notify_task_delegated(
        assignee_user_id="u_ceo",
        previous_assignee_user_id=None,
        task=task,
        principal=principal,
        workspace_name="Acme",
    )
    assert r["reason"] == "self_assign"

    async def boom(*args, **kwargs):
        raise RuntimeError("resend down")

    mock_db = MagicMock()
    mock_db.users.find_one = AsyncMock(return_value={"email": "alex@acme.com"})
    mock_db.memberships.find_one = AsyncMock(return_value=None)
    with patch.object(server, "db", mock_db), \
         patch.object(server, "send_notification_email", new=boom):
        r2 = await server.notify_task_delegated(
            assignee_user_id="u_alex",
            previous_assignee_user_id=None,
            task=task,
            principal=principal,
            workspace_name="Acme",
        )
        assert r2["sent"] is False
        assert r2["reason"] == "error"


@pytest.mark.asyncio
async def test_send_notification_email_wraps_resend():
    with patch.object(server, "send_resend_email", new=AsyncMock(return_value={"sent": True, "id": "e1"})) as mock_send:
        r = await server.send_notification_email("a@b.com", "Hi", "<p>x</p>")
        assert r["sent"] is True
        mock_send.assert_awaited_once()
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to"] == ["a@b.com"]
        assert kwargs["subject"] == "Hi"
