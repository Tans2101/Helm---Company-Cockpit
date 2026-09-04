"""Kalun multi-tenant / roles / OAuth-degradation test suite (iteration 2)."""
import os
import uuid
import time
import pytest
import requests
import pymongo
from datetime import datetime, timezone, timedelta

from conftest import set_workspace_plan

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://exec-cockpit.preview.emergentagent.com").rstrip("/")
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
    s = _sess(OWNER_TOKEN)
    set_workspace_plan(s, BASE_URL, "pro")
    return s


@pytest.fixture(scope="session")
def member():
    return _sess(MEMBER_TOKEN)


@pytest.fixture(scope="session")
def mongo():
    m = pymongo.MongoClient(MONGO_URL)
    return m[DB_NAME]


@pytest.fixture(scope="session")
def fresh_user(mongo):
    """Create a brand-new user + session to test bootstrap + isolation."""
    uid = f"TEST_iso_{uuid.uuid4().hex[:8]}"
    tok = f"TEST_sess_{uuid.uuid4().hex[:10]}"
    email = f"TEST_{uuid.uuid4().hex[:6]}@example.com"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": "Iso User",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    mongo.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                                    "created_at": datetime.now(timezone.utc).isoformat()})
    s = _sess(tok)
    # New behavior: no silent auto-workspace — a fresh owner creates their company.
    s.post(f"{BASE_URL}/api/workspaces", json={"name": "Iso Co"})
    yield {"user_id": uid, "email": email, "session": s}
    # cleanup
    mongo.user_sessions.delete_one({"session_token": tok})
    mems = list(mongo.memberships.find({"user_id": uid}))
    for m in mems:
        mongo.workspaces.delete_one({"workspace_id": m["workspace_id"]})
        mongo.memberships.delete_many({"workspace_id": m["workspace_id"]})
    mongo.users.delete_one({"user_id": uid})


# ---------------- Bootstrap ----------------
def test_bootstrap_new_user_gets_own_workspace_owner(fresh_user):
    r = fresh_user["session"].get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["role"] == "owner"
    assert d["workspace_id"].startswith("ws_")
    # company data seeded
    c = fresh_user["session"].get(f"{BASE_URL}/api/company").json()
    assert c["name"] and c["plan"] == "free"


# ---------------- Isolation ----------------
def test_isolation_fresh_user_vs_owner(fresh_user, owner):
    a = fresh_user["session"].get(f"{BASE_URL}/api/auth/me").json()
    b = owner.get(f"{BASE_URL}/api/auth/me").json()
    assert a["workspace_id"] != b["workspace_id"]
    # Company names should differ
    ca = fresh_user["session"].get(f"{BASE_URL}/api/company").json()
    cb = owner.get(f"{BASE_URL}/api/company").json()
    assert ca["workspace_id"] != cb["workspace_id"]


def test_client_cannot_supply_workspace_id(fresh_user, owner):
    """Even if member sends ?workspace_id=<owner's>, endpoint scopes to caller's active ws."""
    owner_ws = owner.get(f"{BASE_URL}/api/auth/me").json()["workspace_id"]
    r = fresh_user["session"].get(f"{BASE_URL}/api/company?workspace_id={owner_ws}").json()
    assert r["workspace_id"] != owner_ws  # scoped to fresh user's own ws


# ---------------- Shared workspace: owner + member ----------------
def test_owner_and_member_share_workspace(owner, member):
    a = owner.get(f"{BASE_URL}/api/auth/me").json()
    b = member.get(f"{BASE_URL}/api/auth/me").json()
    assert a["workspace_id"] == b["workspace_id"]
    assert a["role"] == "owner" and b["role"] == "member"
    # company name same
    ca = owner.get(f"{BASE_URL}/api/company").json()
    cb = member.get(f"{BASE_URL}/api/company").json()
    assert ca["name"] == cb["name"] and ca["workspace_id"] == cb["workspace_id"]


# ---------------- Invites ----------------
def test_invite_existing_user_auto_joins(owner, mongo):
    # Create a temp existing user
    tmp_uid = f"test_join_{uuid.uuid4().hex[:6]}"
    tmp_email = f"test_join_{uuid.uuid4().hex[:6]}@example.com"
    mongo.users.insert_one({"user_id": tmp_uid, "email": tmp_email, "name": "Joiner",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        r = owner.post(f"{BASE_URL}/api/members/invite", json={"email": tmp_email})
        assert r.status_code == 200, r.text
        assert r.json().get("auto_joined") is True
        # membership row is active
        owner_ws = owner.get(f"{BASE_URL}/api/auth/me").json()["workspace_id"]
        m = mongo.memberships.find_one({"workspace_id": owner_ws, "email": tmp_email})
        assert m and m["status"] == "active" and m["user_id"] == tmp_uid
    finally:
        mongo.memberships.delete_many({"email": tmp_email})
        mongo.users.delete_one({"user_id": tmp_uid})


def test_invite_unregistered_email_creates_pending(owner, mongo):
    email = f"test_pending_{uuid.uuid4().hex[:6]}@example.com"
    r = owner.post(f"{BASE_URL}/api/members/invite", json={"email": email})
    assert r.status_code == 200, r.text
    assert r.json().get("auto_joined") is False
    owner_ws = owner.get(f"{BASE_URL}/api/auth/me").json()["workspace_id"]
    m = mongo.memberships.find_one({"workspace_id": owner_ws, "email": email})
    assert m and m["status"] == "invited"
    # Now create a user with that email + fresh session -> should activate on /auth/me
    uid = f"TEST_pu_{uuid.uuid4().hex[:6]}"
    tok = f"TEST_ptok_{uuid.uuid4().hex[:8]}"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": "Pend",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    mongo.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                                    "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        me = _sess(tok).get(f"{BASE_URL}/api/auth/me").json()
        assert me["workspace_id"] == owner_ws
        assert me["role"] == "member"
        m2 = mongo.memberships.find_one({"workspace_id": owner_ws, "email": email})
        assert m2["status"] == "active" and m2["user_id"] == uid
    finally:
        mongo.memberships.delete_many({"email": email})
        mongo.user_sessions.delete_one({"session_token": tok})
        mongo.users.delete_one({"user_id": uid})


# ---------------- Role-based auth matrix ----------------
OWNER_ONLY_ACTIONS = [
    ("POST", "/api/members/invite", {"email": "test_deny@example.com"}),
    ("POST", "/api/billing/paddle/config", None),
    ("GET",  "/api/integrations/google/connect", None),
    ("POST", "/api/briefing/generate", None),
    ("POST", "/api/reports/weekly-pack", None),
    ("POST", "/api/demo/reset-plan", None),
]


@pytest.mark.parametrize("method,path,body", OWNER_ONLY_ACTIONS)
def test_member_forbidden_on_owner_actions(member, method, path, body):
    if method == "GET":
        r = member.get(f"{BASE_URL}{path}")
    elif method == "POST":
        r = member.post(f"{BASE_URL}{path}", json=body) if body else member.post(f"{BASE_URL}{path}")
    assert r.status_code == 403, f"{path} expected 403 for member, got {r.status_code}: {r.text[:200]}"


def test_member_forbidden_on_decision_action(owner, member):
    decs = owner.get(f"{BASE_URL}/api/decisions").json()["decisions"]
    did = decs[0]["id"]
    r = member.post(f"{BASE_URL}/api/decisions/{did}/action", json={"action": "approved"})
    assert r.status_code == 403


def test_member_forbidden_integration_toggle(owner, member):
    r = member.get(f"{BASE_URL}/api/integrations/google/connect")
    assert r.status_code == 403


MEMBER_READ_OK = [
    "/api/company", "/api/briefing", "/api/decisions", "/api/telemetry",
    "/api/financials", "/api/tasks", "/api/reports",
    "/api/calendar", "/api/people", "/api/integrations", "/api/ask/history",
    "/api/billing/plans", "/api/members", "/api/workspaces",
]


@pytest.mark.parametrize("path", MEMBER_READ_OK)
def test_member_reads_ok(member, path):
    r = member.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} expected 200 for member: {r.status_code}"


def test_member_can_move_task(owner, member):
    items = owner.get(f"{BASE_URL}/api/tasks").json().get("items", [])
    if not items:
        pytest.skip("no tasks")
    tid = items[0]["id"]
    orig = items[0]["column"]
    new_col = "doing" if orig != "doing" else "todo"
    r = member.patch(f"{BASE_URL}/api/tasks/{tid}", json={"column": new_col})
    assert r.status_code == 200, r.text
    # restore
    member.patch(f"{BASE_URL}/api/tasks/{tid}", json={"column": orig})


def test_member_can_ask(member, mongo):
    # clear today's counter to avoid daily-cap collision across runs
    mongo.chat_messages.delete_many({"user_id": "test-user-2", "role": "user"})
    r = member.post(f"{BASE_URL}/api/ask", json={"message": "hi"}, stream=True, timeout=60)
    assert r.status_code == 200
    r.close()


def test_integrations_can_manage_flag(owner, member):
    a = owner.get(f"{BASE_URL}/api/integrations").json()
    b = member.get(f"{BASE_URL}/api/integrations").json()
    assert a["can_manage"] is True
    assert b["can_manage"] is False


# ---------------- Members management ----------------
def test_owner_cannot_change_own_role(owner):
    members = owner.get(f"{BASE_URL}/api/members").json()["members"]
    my = next(m for m in members if m["is_self"])
    r = owner.patch(f"{BASE_URL}/api/members/{my['membership_id']}", json={"pack": "member"})
    assert r.status_code == 400


def test_owner_cannot_remove_self(owner):
    members = owner.get(f"{BASE_URL}/api/members").json()["members"]
    my = next(m for m in members if m["is_self"])
    r = owner.delete(f"{BASE_URL}/api/members/{my['membership_id']}")
    assert r.status_code == 400


def test_owner_change_member_role_and_delete(owner, mongo):
    email = f"test_role_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"TEST_ru_{uuid.uuid4().hex[:6]}"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": "Rolo",
                            "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        owner.post(f"{BASE_URL}/api/members/invite", json={"email": email})
        members = owner.get(f"{BASE_URL}/api/members").json()["members"]
        target = next(m for m in members if m["email"] == email)
        r = owner.patch(f"{BASE_URL}/api/members/{target['membership_id']}", json={"pack": "owner"})
        assert r.status_code == 200
        members2 = owner.get(f"{BASE_URL}/api/members").json()["members"]
        assert next(m for m in members2 if m["email"] == email)["pack"] == "owner"
        # delete
        d = owner.delete(f"{BASE_URL}/api/members/{target['membership_id']}")
        assert d.status_code == 200
    finally:
        mongo.memberships.delete_many({"email": email})
        mongo.users.delete_one({"user_id": uid})


# ---------------- Workspaces ----------------
def test_workspace_list_and_create_and_switch(owner):
    before = owner.get(f"{BASE_URL}/api/workspaces").json()["workspaces"]
    active_before = next(w for w in before if w["active"])
    r = owner.post(f"{BASE_URL}/api/workspaces", json={"name": "TEST_WS_" + uuid.uuid4().hex[:5]})
    assert r.status_code == 200
    new_ws = r.json()["workspace_id"]
    lst = owner.get(f"{BASE_URL}/api/workspaces").json()["workspaces"]
    active = next(w for w in lst if w["active"])
    assert active["workspace_id"] == new_ws  # newly created is active
    assert any(w["workspace_id"] == new_ws and w["role"] == "owner" for w in lst)
    # switch back
    r2 = owner.post(f"{BASE_URL}/api/workspaces/switch", json={"workspace_id": active_before["workspace_id"]})
    assert r2.status_code == 200
    # invalid switch
    r3 = owner.post(f"{BASE_URL}/api/workspaces/switch", json={"workspace_id": "ws_does_not_exist"})
    assert r3.status_code == 404


# ---------------- Integrations OAuth degradation ----------------
def test_integrations_oauth_present(owner):
    d = owner.get(f"{BASE_URL}/api/integrations").json()
    ints = {i["id"]: i for i in d["integrations"]}
    for iid in ["google_calendar", "quickbooks", "gmail", "github"]:
        assert iid in ints, f"integration {iid} missing"
    assert ints["google_calendar"].get("oauth") is True
    assert "configured" in ints["google_calendar"]
    assert "status" in ints["google_calendar"]
    assert "platform" in d
    assert "helm_ai" not in ints


def test_google_connect_returns_expected_shape(owner):
    r = owner.get(f"{BASE_URL}/api/integrations/google/connect")
    assert r.status_code == 200
    d = r.json()
    if d.get("configured"):
        assert d.get("authorization_url", "").startswith("https://accounts.google.com")
    else:
        assert "message" in d


def test_quickbooks_connect_returns_expected_shape(owner):
    r = owner.get(f"{BASE_URL}/api/integrations/quickbooks/connect")
    assert r.status_code == 200
    d = r.json()
    if d.get("configured"):
        assert d.get("authorization_url", "").startswith("https://appcenter.intuit.com")
    else:
        assert "message" in d


# ---------------- Plan gating flip ----------------
def _get_owner_ws(owner):
    return owner.get(f"{BASE_URL}/api/auth/me").json()["workspace_id"]


def test_free_plan_gates(owner):
    owner.post(f"{BASE_URL}/api/demo/reset-plan")
    for path in ["/api/briefing/generate", "/api/reports/weekly-pack"]:
        r = owner.post(f"{BASE_URL}{path}")
        assert r.status_code == 403, f"{path} should 403 on free"
    r = owner.post(f"{BASE_URL}/api/integrations/quickbooks/sync")
    assert r.status_code == 403


def test_pro_plan_enables_briefing_and_weekly(owner, mongo):
    ws = _get_owner_ws(owner)
    mongo.workspaces.update_one({"workspace_id": ws}, {"$set": {"plan": "pro"}})
    try:
        r = owner.post(f"{BASE_URL}/api/briefing/generate", timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert len(r.json().get("ai_summary", "")) > 20
        r2 = owner.post(f"{BASE_URL}/api/reports/weekly-pack", timeout=120)
        assert r2.status_code == 200
        assert len(r2.json().get("content", "")) > 20
    finally:
        owner.post(f"{BASE_URL}/api/demo/reset-plan")


# ---------------- Stripe checkout (removed — Paddle only) ----------------
@pytest.mark.skip(reason="Stripe checkout removed; use Paddle billing tests")
def test_stripe_checkout_owner(owner, mongo):
    r = owner.post(f"{BASE_URL}/api/payments/checkout", json={"origin_url": BASE_URL})
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "checkout_url" in d and "session_id" in d and d["checkout_url"].startswith("http")
    ws = _get_owner_ws(owner)
    tx = mongo.payment_transactions.find_one({"session_id": d["session_id"]})
    assert tx and tx["workspace_id"] == ws


# ---------------- Ask history per (workspace,user) ----------------
def test_ask_history_isolated_per_user(owner, member, mongo):
    mongo.chat_messages.delete_many({"user_id": {"$in": ["test-user-kalun", "test-user-2"]}, "role": "user"})
    # send unique msg from each
    tag_o = f"TESTO_{uuid.uuid4().hex[:6]}"
    tag_m = f"TESTM_{uuid.uuid4().hex[:6]}"
    ro = owner.post(f"{BASE_URL}/api/ask", json={"message": tag_o}, stream=True, timeout=60)
    ro.content  # drain fully to trigger finally save
    ro.close()
    rm = member.post(f"{BASE_URL}/api/ask", json={"message": tag_m}, stream=True, timeout=60)
    rm.content
    rm.close()
    time.sleep(1)
    ho = owner.get(f"{BASE_URL}/api/ask/history").json()["messages"]
    hm = member.get(f"{BASE_URL}/api/ask/history").json()["messages"]
    o_texts = [m["content"] for m in ho]
    m_texts = [m["content"] for m in hm]
    assert any(tag_o in t for t in o_texts)
    assert any(tag_m in t for t in m_texts)
    assert not any(tag_m in t for t in o_texts), "member msg leaked into owner history"
    assert not any(tag_o in t for t in m_texts), "owner msg leaked into member history"
