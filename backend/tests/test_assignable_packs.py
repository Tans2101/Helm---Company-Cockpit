"""Owner/CEO pack is never assignable via invite or role edit."""
import os

os.environ.setdefault("DB_NAME", "test_assignable_packs")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

import pytest
from fastapi import HTTPException


def test_assignable_packs_exclude_owner():
    import server

    assert "owner" in server.VALID_PACKS
    assert "owner" not in server.ASSIGNABLE_PACKS
    assert "exec" in server.ASSIGNABLE_PACKS
    assert "member" in server.ASSIGNABLE_PACKS


def test_require_assignable_pack_rejects_owner():
    import server

    assert server._require_assignable_pack("exec") == "exec"
    with pytest.raises(HTTPException) as ei:
        server._require_assignable_pack("owner")
    assert ei.value.status_code == 400
    assert "ceo" in ei.value.detail.lower() or "owner" in ei.value.detail.lower()


def test_require_assignable_pack_rejects_unknown():
    import server

    with pytest.raises(HTTPException) as ei:
        server._require_assignable_pack("hacker")
    assert ei.value.status_code == 400
