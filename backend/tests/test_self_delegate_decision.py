"""Self-delegation must keep a decision actionable (pending), not terminal."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_self_delegate_decision")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import _decision_owner_is_self, _heal_self_delegated_decisions  # noqa: E402


def test_decision_owner_is_self_myself_and_name():
    principal = {"name": "Ada Lovelace", "email": "ada@helm.test", "user_id": "u1"}
    assert _decision_owner_is_self(principal, "Myself") is True
    assert _decision_owner_is_self(principal, "myself") is True
    assert _decision_owner_is_self(principal, "me") is True
    assert _decision_owner_is_self(principal, "Ada Lovelace") is True
    assert _decision_owner_is_self(principal, "ada@helm.test") is True
    assert _decision_owner_is_self(principal, "Bob") is False
    assert _decision_owner_is_self(principal, "") is False
    assert _decision_owner_is_self(principal, None) is False


def test_heal_self_delegated_rewrites_status_to_pending():
    principal = {"name": "Ada Lovelace", "email": "ada@helm.test"}
    decisions = [
        {"id": "d1", "status": "delegated", "owner": "Myself"},
        {"id": "d2", "status": "delegated", "owner": "Bob"},
        {"id": "d3", "status": "approved", "owner": "Myself"},
        {"id": "d4", "status": "pending", "owner": None},
        {"id": "d5", "status": "delegated", "owner": "Ada Lovelace"},
    ]
    assert _heal_self_delegated_decisions(principal, decisions) is True
    assert decisions[0]["status"] == "pending"
    assert decisions[1]["status"] == "delegated"
    assert decisions[2]["status"] == "approved"
    assert decisions[3]["status"] == "pending"
    assert decisions[4]["status"] == "pending"


def test_heal_noop_when_nothing_stuck():
    principal = {"name": "Ada", "email": "a@x.com"}
    decisions = [
        {"id": "d1", "status": "pending", "owner": "Myself"},
        {"id": "d2", "status": "delegated", "owner": "Other"},
    ]
    assert _heal_self_delegated_decisions(principal, decisions) is False
