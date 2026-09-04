"""Unit tests for Manage Access section helpers and can_section_write grants."""
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

import access_sections as sec_access


def test_normalize_section_grants_filters_and_dedupes():
    assert sec_access.normalize_section_grants(["tasks", "bogus", "Tasks", "decisions", ""]) == [
        "tasks",
        "decisions",
    ]
    assert sec_access.normalize_section_grants(None) == []
    assert sec_access.normalize_section_grants({"tasks": True}) == []


def test_sections_for_perms_maps_pack_perms():
    assert sec_access.sections_for_perms({"finance:write", "read"}) == ["financials"]
    assert "tasks" in sec_access.sections_for_perms({"tasks:assign", "decisions:act"})
    assert "decisions" in sec_access.sections_for_perms({"tasks:assign", "decisions:act"})
    assert sec_access.sections_for_perms({"read", "tasks:move"}) == []


def test_normalize_section_access_keeps_known_sections():
    raw = {
        "tasks": ["Engineering", "engineering", ""],
        "unknown": ["Sales"],
        "sales": "not-a-list",
    }
    out = sec_access.normalize_section_access(raw)
    assert out == {"tasks": ["Engineering"]}


@pytest.mark.asyncio
async def test_can_section_write_honors_member_grants():
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
        "department": "Engineering",
        "section_grants": ["decisions"],
    }

    with patch.object(server, "_membership_for", new=AsyncMock(return_value=membership)):
        with patch.object(server, "get_ws", new=AsyncMock(return_value={"section_access": {}})):
            assert await server.can_section_write(principal, "decisions", "decisions:act") is True
            assert await server.can_section_write(principal, "tasks", "tasks:assign") is False


@pytest.mark.asyncio
async def test_can_section_write_honors_legacy_department_grants():
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
        "department": "Engineering",
        "section_grants": [],
    }
    ws = {"section_access": {"tasks": ["Engineering"]}}

    with patch.object(server, "_membership_for", new=AsyncMock(return_value=membership)):
        with patch.object(server, "get_ws", new=AsyncMock(return_value=ws)):
            assert await server.can_section_write(principal, "tasks", "tasks:assign") is True
            assert await server.can_section_write(principal, "decisions", "decisions:act") is False


@pytest.mark.asyncio
async def test_can_section_write_pack_perm_short_circuits():
    import server

    principal = {
        "user_id": "u_exec",
        "workspace_id": "ws_1",
        "pack": "exec",
    }
    with patch.object(server, "_membership_for", new=AsyncMock(return_value={})) as mem:
        assert await server.can_section_write(principal, "decisions", "decisions:act") is True
        mem.assert_not_called()
