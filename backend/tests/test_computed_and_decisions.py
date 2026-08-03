"""Iteration 5 — computed telemetry/team/reports + decisions CRUD.

Covers:
- Decisions CRUD (POST/PATCH/DELETE with owner=200, member=403; empty title=400) and the pre-existing /action endpoint.
- GET /decisions returns can_act flag.
- GET /telemetry is derived from real data (kpis include Headcount + Open Tasks always; MRR/ARR/Runway/Net Burn only if financials exist).
- GET /team is built from active memberships (real users), utilization + open_tasks + posted_today/blocked from today's updates.
- GET /reports returns exactly 3 computed cards (Financial Snapshot, Team Pulse, Execution).
- POST /reports/weekly-pack still Pro-gated (403 when free).
- GET /onboarding/checklist returns 4 steps with done+route, and complete boolean.
- GET /calendar returns a `live` boolean flag (false for a clean workspace w/o google_tokens).
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

OWNER_TOKEN = "test_session_kalun_123"
MEMBER_TOKEN = "test_session_user2"


def _sess(token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def owner():
    s = _sess(OWNER_TOKEN)
    # Ensure the owner workspace has sample data (financials, people, decisions).
    s.post(f"{BASE_URL}/api/workspace/apply-template", json={"template": "sample"})
    return s


@pytest.fixture(scope="module")
def member():
    return _sess(MEMBER_TOKEN)


# ---------------- Decisions CRUD ----------------

class TestDecisionsCRUD:
    def test_list_returns_can_act_owner(self, owner):
        r = owner.get(f"{BASE_URL}/api/decisions")
        assert r.status_code == 200
        j = r.json()
        assert "decisions" in j and isinstance(j["decisions"], list)
        assert j["can_act"] is True

    def test_list_returns_can_act_member_false(self, member):
        r = member.get(f"{BASE_URL}/api/decisions")
        assert r.status_code == 200
        assert r.json()["can_act"] is False

    def test_owner_create_decision_200_and_persists(self, owner):
        title = f"TEST_DEC_{uuid.uuid4().hex[:6]}"
        payload = {"title": title, "category": "Hiring", "description": "desc",
                   "recommendation": "recc", "confidence": 72, "due": "2026-02-15", "impact": "High"}
        r = owner.post(f"{BASE_URL}/api/decisions", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()["decision"]
        assert d["title"] == title
        assert d["status"] == "pending"
        assert d["impact"] == "High"
        assert d["confidence"] == 72
        # GET back to verify persisted
        lst = owner.get(f"{BASE_URL}/api/decisions").json()["decisions"]
        assert any(x["id"] == d["id"] and x["title"] == title for x in lst)
        # cleanup
        owner.delete(f"{BASE_URL}/api/decisions/{d['id']}")

    def test_owner_create_empty_title_400(self, owner):
        r = owner.post(f"{BASE_URL}/api/decisions", json={"title": "   ", "category": "General", "description": "x"})
        assert r.status_code == 400

    def test_owner_patch_and_delete(self, owner):
        # Create
        r = owner.post(f"{BASE_URL}/api/decisions",
                       json={"title": "TEST_DEC_EDIT", "category": "Ops", "description": "d", "impact": "Low", "confidence": 50})
        did = r.json()["decision"]["id"]
        # Patch
        r2 = owner.patch(f"{BASE_URL}/api/decisions/{did}",
                         json={"title": "TEST_DEC_EDIT2", "category": "Ops", "description": "d2", "impact": "Medium", "confidence": 90})
        assert r2.status_code == 200, r2.text
        # Verify patch persisted
        after = [x for x in owner.get(f"{BASE_URL}/api/decisions").json()["decisions"] if x["id"] == did]
        assert after and after[0]["title"] == "TEST_DEC_EDIT2"
        assert after[0]["impact"] == "Medium"
        assert after[0]["confidence"] == 90
        # Delete
        r3 = owner.delete(f"{BASE_URL}/api/decisions/{did}")
        assert r3.status_code == 200
        # Verify gone
        gone = [x for x in owner.get(f"{BASE_URL}/api/decisions").json()["decisions"] if x["id"] == did]
        assert gone == []

    def test_patch_missing_404(self, owner):
        r = owner.patch(f"{BASE_URL}/api/decisions/does_not_exist",
                        json={"title": "x", "category": "G", "description": "d"})
        assert r.status_code == 404

    def test_member_cannot_create_403(self, member):
        r = member.post(f"{BASE_URL}/api/decisions",
                        json={"title": "TEST_DEC_MEMBER", "category": "G", "description": "d"})
        assert r.status_code == 403

    def test_member_cannot_patch_or_delete_403(self, owner, member):
        # owner creates one for member to attempt to touch
        r = owner.post(f"{BASE_URL}/api/decisions",
                       json={"title": "TEST_DEC_MEMBER_TARGET", "category": "G", "description": "d"})
        did = r.json()["decision"]["id"]
        try:
            r_p = member.patch(f"{BASE_URL}/api/decisions/{did}",
                               json={"title": "hack", "category": "G", "description": "d"})
            r_d = member.delete(f"{BASE_URL}/api/decisions/{did}")
            assert r_p.status_code == 403
            assert r_d.status_code == 403
        finally:
            owner.delete(f"{BASE_URL}/api/decisions/{did}")

    def test_existing_action_endpoint_still_works(self, owner):
        r = owner.post(f"{BASE_URL}/api/decisions",
                       json={"title": "TEST_DEC_ACT", "category": "G", "description": "d"})
        did = r.json()["decision"]["id"]
        try:
            r2 = owner.post(f"{BASE_URL}/api/decisions/{did}/action", json={"action": "approve"})
            assert r2.status_code == 200, r2.text
            after = [x for x in owner.get(f"{BASE_URL}/api/decisions").json()["decisions"] if x["id"] == did]
            assert after and after[0]["status"] in ("approve", "approved")
        finally:
            owner.delete(f"{BASE_URL}/api/decisions/{did}")


# ---------------- Telemetry (computed) ----------------

class TestTelemetryComputed:
    def test_owner_kpis_include_computed_labels(self, owner):
        r = owner.get(f"{BASE_URL}/api/telemetry")
        assert r.status_code == 200
        j = r.json()
        labels = [k["label"] for k in j["kpis"]]
        # Headcount + Open Tasks always
        assert "Headcount" in labels
        assert "Open Tasks" in labels
        # Owner sample workspace has financials seeded => MRR/ARR/Runway/Net Burn present
        assert "MRR" in labels
        assert "ARR" in labels
        assert "Runway" in labels
        assert "Net Burn" in labels
        assert isinstance(j.get("revenue_trend"), list)
        assert "funnel" in j and "risks" in j

    def test_open_tasks_kpi_matches_tasks_data(self, owner):
        tel = owner.get(f"{BASE_URL}/api/telemetry").json()
        open_tasks_kpi = next(k for k in tel["kpis"] if k["label"] == "Open Tasks")["value"]
        # Cross-check against /company (tasks)
        tasks = owner.get(f"{BASE_URL}/api/tasks").json()
        items = tasks.get("items", tasks.get("tasks", [])) if isinstance(tasks, dict) else []
        open_n = len([t for t in items if t.get("column") != "done"])
        assert open_tasks_kpi == str(open_n)

    def test_headcount_kpi_is_a_number_string(self, owner):
        tel = owner.get(f"{BASE_URL}/api/telemetry").json()
        hc = next(k for k in tel["kpis"] if k["label"] == "Headcount")["value"]
        assert hc.isdigit()


# ---------------- Team (computed) ----------------

class TestTeamComputed:
    def test_team_members_from_active_memberships(self, owner):
        r = owner.get(f"{BASE_URL}/api/team")
        assert r.status_code == 200
        j = r.json()
        assert "members" in j and isinstance(j["members"], list)
        assert "avg_utilization" in j
        assert "overloaded_count" in j
        # Cross-check: members count should equal active memberships count
        mems = owner.get(f"{BASE_URL}/api/members").json()
        active = [m for m in (mems.get("members") or []) if m.get("status") == "active"]
        assert len(j["members"]) == len(active)
        for m in j["members"]:
            for k in ("name", "role", "utilization", "status", "open_tasks", "posted_today", "blocked"):
                assert k in m


# ---------------- Reports (computed) ----------------

class TestReportsComputed:
    def test_reports_returns_three_computed_cards(self, owner):
        r = owner.get(f"{BASE_URL}/api/reports")
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j["reports"], list) and len(j["reports"]) == 3
        titles = [x["title"] for x in j["reports"]]
        assert titles == ["Financial Snapshot", "Team Pulse", "Execution"]
        for card in j["reports"]:
            assert "summary" in card and card["summary"]
            assert "metrics" in card and len(card["metrics"]) >= 3

    def test_weekly_pack_is_pro_gated_403_when_free(self, owner):
        # Ensure plan reset to free
        owner.post(f"{BASE_URL}/api/demo/reset-plan")
        r = owner.post(f"{BASE_URL}/api/reports/weekly-pack")
        assert r.status_code == 403


# ---------------- Onboarding checklist ----------------

class TestOnboardingChecklist:
    def test_checklist_returns_four_steps(self, owner):
        r = owner.get(f"{BASE_URL}/api/onboarding/checklist")
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j["steps"], list) and len(j["steps"]) == 4
        ids = [s["id"] for s in j["steps"]]
        assert ids == ["financials", "people", "invite", "update"]
        for s in j["steps"]:
            assert "label" in s and "route" in s and isinstance(s["done"], bool)
        assert isinstance(j["complete"], bool)

    def test_owner_workspace_financials_and_people_done(self, owner):
        j = owner.get(f"{BASE_URL}/api/onboarding/checklist").json()
        by_id = {s["id"]: s for s in j["steps"]}
        # Owner sample data has financials + 6 people
        assert by_id["financials"]["done"] is True
        assert by_id["people"]["done"] is True


# ---------------- Calendar (live flag) ----------------

class TestCalendarLiveFlag:
    def test_calendar_returns_live_flag(self, owner):
        r = owner.get(f"{BASE_URL}/api/calendar")
        assert r.status_code == 200
        j = r.json()
        assert "live" in j
        assert isinstance(j["live"], bool)
