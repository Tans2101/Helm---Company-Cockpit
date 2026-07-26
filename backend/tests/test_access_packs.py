"""Access packs: owner / exec / finance / hr / member — module scoping + finance activity rollup."""
import os
import uuid
import pytest
import requests
import pymongo
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://exec-cockpit.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
OWNER_TOKEN = "test_session_kalun_123"
MEMBER_TOKEN = "test_session_user2"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _sess(token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def owner():
    return _sess(OWNER_TOKEN)


@pytest.fixture(scope="session")
def member():
    return _sess(MEMBER_TOKEN)


@pytest.fixture(scope="session")
def mongo():
    return pymongo.MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture
def finance_user(owner, mongo):
    """Invite a finance-pack user into the owner's workspace."""
    email = f"test_fin_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"TEST_fin_{uuid.uuid4().hex[:6]}"
    tok = f"TEST_ftok_{uuid.uuid4().hex[:8]}"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": "Fin Operator",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    mongo.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                                    "created_at": datetime.now(timezone.utc).isoformat()})
    r = owner.post(f"{API}/members/invite", json={"email": email, "role": "finance"})
    assert r.status_code == 200, r.text
    # activate via /auth/me
    sess = _sess(tok)
    me = sess.get(f"{API}/auth/me").json()
    assert me["role"] == "finance"
    yield {"session": sess, "email": email, "user_id": uid, "token": tok, "workspace_id": me["workspace_id"]}
    owner_ws = owner.get(f"{API}/auth/me").json()["workspace_id"]
    mongo.memberships.delete_many({"email": email, "workspace_id": owner_ws})
    mongo.user_sessions.delete_one({"session_token": tok})
    mongo.users.delete_one({"user_id": uid})
    mongo.activity_events.delete_many({"actor_user_id": uid})


def test_auth_me_exposes_pack_fields(owner):
    me = owner.get(f"{API}/auth/me").json()
    assert me["role"] == "owner"
    assert "finance:write" in me["perms"]
    assert me["modules"] == []
    assert me["home"] == "/app"


def test_member_no_longer_writes_finance(member):
    r = member.get(f"{API}/financials")
    assert r.status_code == 200
    assert r.json()["can_write"] is False
    r2 = member.post(f"{API}/financials/entries", json={
        "type": "revenue", "category": "x", "amount": 1, "month": "2025-01",
    })
    assert r2.status_code == 403


def test_finance_pack_scoped_nav_apis(finance_user):
    s = finance_user["session"]
    assert s.get(f"{API}/financials").status_code == 200
    assert s.get(f"{API}/briefing").status_code == 200
    assert s.get(f"{API}/tasks").status_code == 200
    # out of pack
    assert s.get(f"{API}/decisions").status_code == 403
    assert s.get(f"{API}/people").status_code == 403
    assert s.get(f"{API}/members").status_code == 403
    assert s.get(f"{API}/integrations").status_code == 403
    fin = s.get(f"{API}/financials").json()
    assert fin["can_write"] is True


def test_finance_write_rolls_into_briefing_what_changed(finance_user, owner):
    s = finance_user["session"]
    payload = {"type": "revenue", "category": "TEST_activity_cat", "amount": 2500,
               "month": "2025-11", "recurring": False, "note": "activity test"}
    r = s.post(f"{API}/financials/entries", json=payload)
    assert r.status_code == 200, r.text
    eid = r.json()["entry"]["id"]
    try:
        b = owner.get(f"{API}/briefing").json()
        titles = [c["title"] for c in b.get("what_changed", [])]
        assert any("Logged revenue" in t and "TEST_activity_cat" in t for t in titles), titles
    finally:
        s.delete(f"{API}/financials/entries/{eid}")


def test_invite_and_change_pack(owner, mongo):
    email = f"test_pack_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"TEST_pack_{uuid.uuid4().hex[:6]}"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": "Packer",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        r = owner.post(f"{API}/members/invite", json={"email": email, "role": "hr"})
        assert r.status_code == 200
        assert r.json()["role"] == "hr"
        members = owner.get(f"{API}/members").json()["members"]
        target = next(m for m in members if m["email"] == email)
        assert target["role"] == "hr"
        r2 = owner.patch(f"{API}/members/{target['membership_id']}", json={"role": "exec"})
        assert r2.status_code == 200
        assert r2.json()["role"] == "exec"
        members2 = owner.get(f"{API}/members").json()["members"]
        assert next(m for m in members2 if m["email"] == email)["role"] == "exec"
        assert "packs" in owner.get(f"{API}/members").json()
    finally:
        mongo.memberships.delete_many({"email": email})
        mongo.users.delete_one({"user_id": uid})


def test_role_toggle_owner_member_still_works(owner, mongo):
    """Backward-compat: owner ↔ member still valid packs."""
    email = f"test_om_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"TEST_om_{uuid.uuid4().hex[:6]}"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": "OM",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        owner.post(f"{API}/members/invite", json={"email": email, "role": "member"})
        members = owner.get(f"{API}/members").json()["members"]
        target = next(m for m in members if m["email"] == email)
        r = owner.patch(f"{API}/members/{target['membership_id']}", json={"role": "owner"})
        assert r.status_code == 200
        r2 = owner.patch(f"{API}/members/{target['membership_id']}", json={"role": "member"})
        assert r2.status_code == 200
    finally:
        mongo.memberships.delete_many({"email": email})
        mongo.users.delete_one({"user_id": uid})
