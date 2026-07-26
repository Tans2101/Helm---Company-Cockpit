"""Local unit tests for audit hardening helpers (no live preview required)."""
import os
import sys
from pathlib import Path

import pytest

# server.py expects Mongo env at import time
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def test_origin_allowed_localhost():
    assert server._origin_allowed("http://localhost:3000")
    assert server._origin_allowed("http://127.0.0.1:3000/")
    assert not server._origin_allowed("https://evil.example")
    assert not server._origin_allowed("javascript:alert(1)")


def test_origin_allowed_emergent_preview():
    assert server._origin_allowed("https://exec-cockpit.preview.emergentagent.com")
    assert not server._origin_allowed("https://evil.com")


def test_join_code_entropy():
    code = server._new_join_code()
    assert len(code) == 12
    assert code.isalnum()
    assert code.isupper()


def test_oauth_state_roundtrip_binds_user():
    state = server._sign_state("google", "ws_abc", "user_1")
    verified = server._verify_state(state)
    assert verified == ("google", "ws_abc", "user_1")
    assert server._verify_state("tampered") is None


def test_join_rate_limit():
    uid = "rate_limit_user_test"
    server._JOIN_ATTEMPTS.pop(uid, None)
    for _ in range(server._JOIN_LIMIT):
        server._rate_limit_join(uid)
    with pytest.raises(Exception) as ei:
        server._rate_limit_join(uid)
    assert ei.value.status_code == 429
    server._JOIN_ATTEMPTS.pop(uid, None)
