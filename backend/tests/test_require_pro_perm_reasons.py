"""require_pro_perm distinguishes permission vs plan 403 bodies."""
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_require_pro_perm_reasons")

import server  # noqa: E402


@pytest.mark.asyncio
async def test_require_pro_perm_permission_reason():
    dep = server.require_pro_perm("ask:use")
    principal = {"pack": "member", "workspace_id": "ws1", "user_id": "u1"}
    # Strip ask:use from pack perms for this assertion
    with patch.object(server, "perms_for", return_value=set(server.BASE_PERMS) - {"ask:use"}):
        with pytest.raises(HTTPException) as ei:
            await dep(principal)
    assert ei.value.status_code == 403
    assert ei.value.detail["reason"] == "permission"
    assert "permission" in ei.value.detail["message"].lower()


@pytest.mark.asyncio
async def test_require_pro_perm_plan_reason_for_ask():
    dep = server.require_pro_perm("ask:use")
    principal = {"pack": "owner", "workspace_id": "ws1", "user_id": "u1"}
    with patch.object(server, "BILLING_ENFORCED", True), patch.object(
        server, "get_ws", new=AsyncMock(return_value={"plan": "free"}),
    ), patch.object(server, "workspace_allows", return_value=False):
        with pytest.raises(HTTPException) as ei:
            await dep(principal)
    assert ei.value.status_code == 403
    assert ei.value.detail["reason"] == "plan"
    assert "Ask Helm" in ei.value.detail["message"]
    assert ei.value.detail.get("feature") == "ask_helm"
