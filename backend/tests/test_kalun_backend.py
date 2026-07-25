"""Kalun CEO OS backend test suite."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://exec-cockpit.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_kalun_123"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth(client):
    c = requests.Session()
    c.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    return c


# ---- Auth guard ----
READ_ENDPOINTS = [
    "/api/company", "/api/briefing", "/api/decisions", "/api/telemetry",
    "/api/financials", "/api/tasks", "/api/reports", "/api/team",
    "/api/calendar", "/api/people", "/api/integrations", "/api/ask/history",
    "/api/billing/plans",
]


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_unauth_returns_401(client, path):
    r = client.get(f"{BASE_URL}{path}")
    assert r.status_code == 401, f"{path} expected 401, got {r.status_code}"


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_auth_returns_200(auth, path):
    r = auth.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} expected 200, got {r.status_code}: {r.text[:200]}"
    assert r.json() is not None


# ---- Data shape ----
def test_company_shape(auth):
    d = auth.get(f"{BASE_URL}/api/company").json()
    for k in ["name", "plan", "stage", "employees", "founded", "mission", "ceo_name"]:
        assert k in d
    assert d["name"] == "Northwind Robotics"


def test_briefing_shape(auth):
    d = auth.get(f"{BASE_URL}/api/briefing").json()
    for k in ["metrics", "what_changed", "what_to_decide", "what_to_delegate", "is_pro"]:
        assert k in d, f"missing {k}: keys={list(d.keys())}"


def test_decisions_shape(auth):
    d = auth.get(f"{BASE_URL}/api/decisions").json()
    assert "decisions" in d and isinstance(d["decisions"], list) and len(d["decisions"]) > 0
    for dec in d["decisions"]:
        assert "id" in dec and "status" in dec


def test_tasks_shape(auth):
    d = auth.get(f"{BASE_URL}/api/tasks").json()
    assert "items" in d or "columns" in d


def test_integrations_shape(auth):
    d = auth.get(f"{BASE_URL}/api/integrations").json()
    assert "integrations" in d and isinstance(d["integrations"], list)


# ---- Decision action ----
def test_decision_action_updates_status(auth):
    decs = auth.get(f"{BASE_URL}/api/decisions").json()["decisions"]
    did = decs[0]["id"]
    r = auth.post(f"{BASE_URL}/api/decisions/{did}/action", json={"action": "approved"})
    assert r.status_code == 200, r.text
    updated = auth.get(f"{BASE_URL}/api/decisions").json()["decisions"]
    match = [x for x in updated if x["id"] == did][0]
    assert match["status"] == "approved"


# ---- Task move ----
def test_task_move_persists(auth):
    tasks = auth.get(f"{BASE_URL}/api/tasks").json()
    items = tasks.get("items", [])
    if not items:
        pytest.skip("no tasks")
    tid = items[0]["id"]
    original = items[0]["column"]
    new_col = "doing" if original != "doing" else "todo"
    r = auth.patch(f"{BASE_URL}/api/tasks/{tid}", json={"column": new_col})
    assert r.status_code == 200
    updated = auth.get(f"{BASE_URL}/api/tasks").json()["items"]
    match = [x for x in updated if x["id"] == tid][0]
    assert match["column"] == new_col
    # restore
    auth.patch(f"{BASE_URL}/api/tasks/{tid}", json={"column": original})


# ---- Free plan gating ----
def _ensure_free(auth):
    r = auth.post(f"{BASE_URL}/api/demo/reset-plan")
    assert r.status_code == 200


def test_free_plan_gates_briefing_generate(auth):
    _ensure_free(auth)
    r = auth.post(f"{BASE_URL}/api/briefing/generate")
    assert r.status_code == 403


def test_free_plan_gates_weekly_pack(auth):
    _ensure_free(auth)
    r = auth.post(f"{BASE_URL}/api/reports/weekly-pack")
    assert r.status_code == 403


def test_free_plan_gates_integration_toggle(auth):
    _ensure_free(auth)
    ints = auth.get(f"{BASE_URL}/api/integrations").json()["integrations"]
    r = auth.post(f"{BASE_URL}/api/integrations/{ints[0]['id']}/toggle")
    assert r.status_code == 403


# ---- Ask Kalun (streaming) ----
def test_ask_kalun_streams(auth):
    _ensure_free(auth)
    r = auth.post(f"{BASE_URL}/api/ask", json={"message": "One-sentence health check."}, stream=True, timeout=60)
    assert r.status_code == 200, r.text[:300]
    collected = b""
    for chunk in r.iter_content(chunk_size=None):
        collected += chunk
        if len(collected) > 5:
            break
    r.close()
    assert len(collected) > 0


def test_ask_history_returns_messages(auth):
    r = auth.get(f"{BASE_URL}/api/ask/history")
    assert r.status_code == 200
    assert "messages" in r.json()


# ---- Stripe checkout ----
def test_checkout_creates_session(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout",
                  json={"origin_url": "https://exec-cockpit.preview.emergentagent.com"})
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert "checkout_url" in d and "session_id" in d
    assert d["checkout_url"].startswith("http")
    # status endpoint
    s = auth.get(f"{BASE_URL}/api/payments/status/{d['session_id']}")
    assert s.status_code == 200
    sd = s.json()
    assert sd["session_id"] == d["session_id"]
    assert sd["status"] in ["initiated", "completed"]


# ---- Demo reset ----
def test_demo_reset_plan(auth):
    r = auth.post(f"{BASE_URL}/api/demo/reset-plan")
    assert r.status_code == 200
    plan = auth.get(f"{BASE_URL}/api/company").json()["plan"]
    assert plan == "free"


# ---- Pro plan positive flow ----
def test_pro_plan_enables_gated_endpoints(auth):
    # Flip to pro directly
    import pymongo
    m = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    dbn = os.environ.get("DB_NAME", "test_database")
    m[dbn].company.update_one({"company_id": "kalun-demo"}, {"$set": {"plan": "pro"}})
    try:
        r = auth.post(f"{BASE_URL}/api/briefing/generate", timeout=90)
        assert r.status_code == 200, r.text[:500]
        assert "ai_summary" in r.json() and len(r.json()["ai_summary"]) > 20
    finally:
        auth.post(f"{BASE_URL}/api/demo/reset-plan")
