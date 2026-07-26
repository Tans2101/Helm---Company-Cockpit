"""Department operator loops: HR roster, Sales pipeline, Ops risks → Briefing activity."""
import os
import uuid
import pytest
import requests
import pymongo
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://exec-cockpit.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
OWNER_TOKEN = "test_session_kalun_123"

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
def mongo():
    return pymongo.MongoClient(MONGO_URL)[DB_NAME]


def _make_pack_user(owner, mongo, role, name="Op"):
    email = f"test_{role}_{uuid.uuid4().hex[:6]}@example.com"
    uid = f"TEST_{role}_{uuid.uuid4().hex[:6]}"
    tok = f"TEST_{role}tok_{uuid.uuid4().hex[:8]}"
    mongo.users.insert_one({"user_id": uid, "email": email, "name": name,
                            "created_at": datetime.now(timezone.utc).isoformat()})
    mongo.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                                    "created_at": datetime.now(timezone.utc).isoformat()})
    r = owner.post(f"{API}/members/invite", json={"email": email, "role": role})
    assert r.status_code == 200, r.text
    sess = _sess(tok)
    me = sess.get(f"{API}/auth/me").json()
    assert me["role"] == role
    return {"session": sess, "email": email, "user_id": uid, "token": tok, "workspace_id": me["workspace_id"]}


def _cleanup_pack_user(owner, mongo, info):
    owner_ws = owner.get(f"{API}/auth/me").json()["workspace_id"]
    mongo.memberships.delete_many({"email": info["email"], "workspace_id": owner_ws})
    mongo.user_sessions.delete_one({"session_token": info["token"]})
    mongo.users.delete_one({"user_id": info["user_id"]})
    mongo.activity_events.delete_many({"actor_user_id": info["user_id"]})


@pytest.fixture
def hr_user(owner, mongo):
    info = _make_pack_user(owner, mongo, "hr", "HR Lead")
    yield info
    _cleanup_pack_user(owner, mongo, info)


@pytest.fixture
def sales_user(owner, mongo):
    info = _make_pack_user(owner, mongo, "sales", "Sales Lead")
    yield info
    _cleanup_pack_user(owner, mongo, info)


@pytest.fixture
def ops_user(owner, mongo):
    info = _make_pack_user(owner, mongo, "ops", "Ops Lead")
    yield info
    _cleanup_pack_user(owner, mongo, info)


def test_hr_can_crud_people_and_feeds_briefing(hr_user, owner):
    s = hr_user["session"]
    assert s.get(f"{API}/people").status_code == 200
    assert s.get(f"{API}/people").json()["can_write"] is True
    assert s.get(f"{API}/financials").status_code == 403

    payload = {"name": "TEST Neo Hire", "role": "Analyst", "department": "HR",
               "trust_score": 85, "quality": "A-", "tasks_done": 3, "tenure": "0.1y"}
    r = s.post(f"{API}/people", json=payload)
    assert r.status_code == 200, r.text
    pid = r.json()["person"]["id"]
    headcount = r.json()["headcount"]

    try:
        b = owner.get(f"{API}/briefing").json()
        titles = [c["title"] for c in b.get("what_changed", [])]
        assert any("TEST Neo Hire" in t for t in titles), titles
        assert any(m["label"] == "Headcount" and m["value"] == str(headcount) for m in b["metrics"])

        r2 = s.patch(f"{API}/people/{pid}", json={**payload, "trust_score": 90, "role": "Senior Analyst"})
        assert r2.status_code == 200
        people = s.get(f"{API}/people").json()["people"]
        got = next(p for p in people if p["id"] == pid)
        assert got["trust_score"] == 90 and got["role"] == "Senior Analyst"
    finally:
        s.delete(f"{API}/people/{pid}")


def test_sales_updates_pipeline(sales_user, owner):
    s = sales_user["session"]
    assert s.get(f"{API}/telemetry").status_code == 200
    assert s.get(f"{API}/telemetry").json()["can_write_sales"] is True
    assert s.get(f"{API}/people").status_code == 403

    r = s.put(f"{API}/telemetry/sales", json={
        "pipeline": "$2.1M", "pipeline_delta": 8.5,
        "customers": "420",
        "funnel": [{"stage": "Leads", "value": 1000}, {"stage": "Closed Won", "value": 40}],
    })
    assert r.status_code == 200, r.text
    tel = s.get(f"{API}/telemetry").json()
    pipe = next(k for k in tel["kpis"] if k["label"] == "Pipeline")
    assert pipe["value"] == "$2.1M"
    assert any(f["stage"] == "Leads" and f["value"] == 1000 for f in tel["funnel"])
    b = owner.get(f"{API}/briefing").json()
    assert any("pipeline" in c["title"].lower() for c in b.get("what_changed", []))


def test_ops_risk_crud(ops_user, owner):
    s = ops_user["session"]
    assert s.get(f"{API}/telemetry").json()["can_write_ops"] is True
    r = s.post(f"{API}/telemetry/risks", json={
        "name": "TEST vendor delay", "likelihood": 4, "impact": 3, "category": "Ops",
    })
    assert r.status_code == 200, r.text
    rid = r.json()["risk"]["id"]
    try:
        r2 = s.patch(f"{API}/telemetry/risks/{rid}", json={
            "name": "TEST vendor delay", "likelihood": 5, "impact": 4, "category": "Ops",
        })
        assert r2.status_code == 200
        risks = s.get(f"{API}/telemetry").json()["risks"]
        got = next(x for x in risks if x["id"] == rid)
        assert got["likelihood"] == 5 and got["impact"] == 4
        b = owner.get(f"{API}/briefing").json()
        assert any("TEST vendor delay" in c["title"] for c in b.get("what_changed", []))
    finally:
        assert s.delete(f"{API}/telemetry/risks/{rid}").status_code == 200


def test_pack_homes(hr_user, sales_user, ops_user):
    assert hr_user["session"].get(f"{API}/auth/me").json()["home"] == "/app/people"
    assert sales_user["session"].get(f"{API}/auth/me").json()["home"] == "/app/telemetry"
    assert ops_user["session"].get(f"{API}/auth/me").json()["home"] == "/app/tasks"
