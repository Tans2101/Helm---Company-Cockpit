"""Calendar write permission: pack + section grants, not hardcoded can_write."""
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DB_NAME", "test_calendar_write_perms")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

import access_sections as sec_access


def test_calendar_is_manageable_section():
    assert "calendar" in sec_access.MANAGEABLE_SECTION_IDS
    assert sec_access.section_pack_perm("calendar") == "calendar:write"
    assert "calendar" in sec_access.sections_for_perms({"calendar:write"})


def test_owner_and_exec_have_calendar_write_pack_perm():
    import server

    assert "calendar:write" in server.perms_for("owner")
    assert "calendar:write" in server.perms_for("exec")
    assert "calendar:write" not in server.perms_for("member")
    assert "calendar:write" not in server.perms_for("finance")


@pytest.mark.asyncio
async def test_can_section_write_calendar_via_member_grant():
    import server

    principal = {
        "user_id": "u_member",
        "workspace_id": "ws_1",
        "pack": "member",
    }
    membership = {
        "user_id": "u_member",
        "workspace_id": "ws_1",
        "status": "active",
        "department": "General",
        "section_grants": ["calendar"],
    }

    with patch.object(server, "_membership_for", new=AsyncMock(return_value=membership)):
        with patch.object(server, "get_ws", new=AsyncMock(return_value={"section_access": {}})):
            assert await server.can_section_write(principal, "calendar", "calendar:write") is True
            assert await server.can_section_write(principal, "financials", "finance:write") is False


@pytest.mark.asyncio
async def test_member_without_calendar_grant_cannot_write():
    import server

    principal = {
        "user_id": "u_member",
        "workspace_id": "ws_1",
        "pack": "member",
    }
    membership = {
        "user_id": "u_member",
        "workspace_id": "ws_1",
        "status": "active",
        "department": "General",
        "section_grants": [],
    }

    with patch.object(server, "_membership_for", new=AsyncMock(return_value=membership)):
        with patch.object(server, "get_ws", new=AsyncMock(return_value={"section_access": {}})):
            assert await server.can_section_write(principal, "calendar", "calendar:write") is False
