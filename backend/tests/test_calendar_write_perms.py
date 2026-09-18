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


def test_owner_can_manage_any_helm_event():
    import server

    owner = {"user_id": "u_ceo", "pack": "owner"}
    other = {"id": "helm_1", "source": "helm", "created_by": "u_other", "title": "Standup"}
    assert server.can_manage_helm_calendar_event(owner, other) is True


def test_exec_can_manage_any_helm_event():
    import server

    exec_p = {"user_id": "u_exec", "pack": "exec"}
    other = {"id": "helm_1", "source": "helm", "created_by": "u_other", "title": "Standup"}
    assert server.can_manage_helm_calendar_event(exec_p, other) is True


def test_grant_member_can_only_manage_own_events():
    import server

    member = {"user_id": "u_member", "pack": "member"}
    own = {"id": "helm_1", "source": "helm", "created_by": "u_member", "title": "Mine"}
    other = {"id": "helm_2", "source": "helm", "created_by": "u_other", "title": "Theirs"}
    assert server.can_manage_helm_calendar_event(member, own, accessible_department_ids=set()) is True
    assert server.can_manage_helm_calendar_event(member, other, accessible_department_ids=set()) is False


def test_grant_member_can_manage_department_tied_event():
    import server

    member = {"user_id": "u_member", "pack": "member"}
    sales_event = {
        "id": "helm_sales",
        "source": "helm",
        "created_by": "u_other",
        "department_id": "dept_sales",
        "department_ids": ["dept_sales"],
        "title": "Pipeline review",
    }
    assert server.can_manage_helm_calendar_event(
        member, sales_event, accessible_department_ids={"dept_sales"},
    ) is True
    assert server.can_manage_helm_calendar_event(
        member, sales_event, accessible_department_ids={"dept_hr"},
    ) is False


def test_legacy_helm_event_without_creator_editable_by_grant_writer():
    import server

    member = {"user_id": "u_member", "pack": "member"}
    legacy = {"id": "helm_old", "source": "helm", "title": "Old"}
    assert server.can_manage_helm_calendar_event(member, legacy, accessible_department_ids=set()) is True


def test_deadline_events_not_manageable():
    import server

    owner = {"user_id": "u_ceo", "pack": "owner"}
    deadline = {"id": "deadline_x", "source": "deadline", "created_by": "u_ceo"}
    assert server.can_manage_helm_calendar_event(owner, deadline) is False


def test_annotate_sets_can_edit_flags():
    import server

    principal = {"user_id": "u_member", "pack": "member"}
    events = [
        {"id": "helm_1", "source": "helm", "created_by": "u_member", "title": "Mine"},
        {"id": "helm_2", "source": "helm", "created_by": "u_other", "title": "Theirs"},
        {
            "id": "helm_3",
            "source": "helm",
            "created_by": "u_other",
            "department_ids": ["dept_sales"],
            "title": "Sales",
        },
        {"id": "deadline_1", "source": "deadline", "title": "Due"},
    ]
    annotated = server._annotate_helm_event_permissions(
        principal, events, can_write=True, accessible_department_ids={"dept_sales"},
    )
    assert annotated[0]["can_edit"] is True
    assert annotated[1]["can_edit"] is False
    assert annotated[2]["can_edit"] is True
    assert annotated[3]["can_edit"] is False

    locked = server._annotate_helm_event_permissions(
        principal, events, can_write=False, accessible_department_ids={"dept_sales"},
    )
    assert all(row["can_edit"] is False for row in locked)


def test_build_helm_event_stamps_created_by_and_departments():
    import server

    payload = server.CalendarEventInput(title="Kickoff", date="2026-09-18", time="10:00")
    ev = server._build_helm_event(
        payload, created_by="u_member", department_ids=["dept_sales", "dept_hr"],
    )
    assert ev["created_by"] == "u_member"
    assert ev["source"] == "helm"
    assert ev["department_ids"] == ["dept_sales", "dept_hr"]
    assert ev["department_id"] == "dept_sales"

    edited = server._build_helm_event(
        payload,
        event_id=ev["id"],
        preserve=ev,
    )
    assert edited["created_by"] == "u_member"
    assert edited["department_ids"] == ["dept_sales", "dept_hr"]