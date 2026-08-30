"""Iteration 6 tests: Paddle Billing.

Webhook POSTs are sent to the LOCAL app (localhost:8001) because the preview
ingress/WAF blocks unauthenticated programmatic POSTs to /api/webhook/paddle
(returns 403 before reaching the app). The deployed environment is unaffected.
Signature-verification, idempotency and nonce-binding are the security-critical paths.
"""
import os
import time
import hmac
import hashlib
import json
import uuid

import pytest
import pymongo
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://exec-cockpit.preview.emergentagent.com").rstrip("/")
LOCAL = "http://localhost:8001"
OWNER_TOKEN = "test_session_kalun_123"
MEMBER_TOKEN = "test_session_user2"
WS_ID = "ws_d6b4d8c892fb"
SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo():
    return pymongo.MongoClient(MONGO_URL)[DB_NAME]


def _sign(raw: bytes):
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "Paddle-Signature": f"ts={ts};h1={sig}"}


def _config():
    r = requests.post(f"{BASE_URL}/api/billing/paddle/config", headers=_h(OWNER_TOKEN))
    return r


def test_secret_present():
    assert SECRET, "PADDLE_WEBHOOK_SECRET must be set in backend/.env"


def test_billing_plans_paddle_ready():
    d = requests.get(f"{BASE_URL}/api/billing/plans", headers=_h(OWNER_TOKEN)).json()
    assert d["paddle_ready"] is True


def test_config_requires_billing_manage():
    r = requests.post(f"{BASE_URL}/api/billing/paddle/config", headers=_h(MEMBER_TOKEN))
    assert r.status_code == 403


def test_config_returns_token_and_nonce(mongo):
    r = _config()
    assert r.status_code == 200
    d = r.json()
    assert d["client_token"] and d["price_id"]
    assert d["environment"] in ("sandbox", "production")
    assert d["workspace_id"] == WS_ID
    intent = mongo.paddle_intents.find_one({"_id": d["checkout_nonce"]})
    assert intent and intent["workspace_id"] == WS_ID and intent["used"] is False


def test_webhook_bad_signature_400():
    body = json.dumps({"event_id": "evt_bad", "event_type": "transaction.completed"}).encode()
    r = requests.post(f"{LOCAL}/api/webhook/paddle", data=body,
                      headers={"Content-Type": "application/json", "Paddle-Signature": "ts=123;h1=deadbeef"})
    assert r.status_code == 400


def test_webhook_provisions_pro_and_is_idempotent(mongo):
    # ensure free first
    requests.post(f"{BASE_URL}/api/demo/reset-plan", headers=_h(OWNER_TOKEN))
    nonce = _config().json()["checkout_nonce"]
    eid = f"evt_{uuid.uuid4().hex[:10]}"
    mongo.paddle_events.delete_one({"_id": eid})
    body = json.dumps({
        "event_id": eid, "event_type": "transaction.completed", "occurred_at": "2026-07-26T00:00:00Z",
        "data": {"id": "txn_x", "subscription_id": "sub_x", "customer_id": "ctm_x",
                 "custom_data": {"checkout_nonce": nonce, "workspace_id": WS_ID, "user_id": "test-user-kalun"}},
    }).encode()
    hdr = _sign(body)
    r1 = requests.post(f"{LOCAL}/api/webhook/paddle", data=body, headers=hdr)
    assert r1.status_code == 200 and r1.json()["received"] is True
    # provisioned
    ws = mongo.workspaces.find_one({"workspace_id": WS_ID})
    assert ws["plan"] == "pro" and ws.get("billing_provider") == "paddle"
    # replay same event -> idempotent (no error), still one event stored
    r2 = requests.post(f"{LOCAL}/api/webhook/paddle", data=body, headers=hdr)
    assert r2.status_code == 200
    assert mongo.paddle_events.count_documents({"_id": eid}) == 1
    # cleanup
    mongo.paddle_events.delete_one({"_id": eid})
    requests.post(f"{BASE_URL}/api/demo/reset-plan", headers=_h(OWNER_TOKEN))


def test_webhook_nonce_binding_blocks_cross_workspace(mongo):
    requests.post(f"{BASE_URL}/api/demo/reset-plan", headers=_h(OWNER_TOKEN))
    nonce = _config().json()["checkout_nonce"]  # bound to WS_ID
    eid = f"evt_{uuid.uuid4().hex[:10]}"
    body = json.dumps({
        "event_id": eid, "event_type": "transaction.completed",
        "data": {"id": "txn_y", "custom_data": {"checkout_nonce": nonce,
                 "workspace_id": "ws_SOMEONE_ELSE", "user_id": "test-user-kalun"}},
    }).encode()
    r = requests.post(f"{LOCAL}/api/webhook/paddle", data=body, headers=_sign(body))
    assert r.status_code == 200  # accepted but must NOT provision the wrong ws
    ws = mongo.workspaces.find_one({"workspace_id": WS_ID})
    assert ws["plan"] == "free", "cross-workspace nonce must not provision"
    assert mongo.workspaces.find_one({"workspace_id": "ws_SOMEONE_ELSE"}) is None
    mongo.paddle_events.delete_one({"_id": eid})


def test_webhook_subscription_canceled_downgrades(mongo):
    sub_id = "sub_cancel_test"
    mongo.workspaces.update_one(
        {"workspace_id": WS_ID},
        {"$set": {"plan": "pro", "paddle_subscription_id": sub_id, "subscription_status": "active"}},
    )
    eid = f"evt_{uuid.uuid4().hex[:10]}"
    mongo.paddle_events.delete_one({"_id": eid})
    body = json.dumps({
        "event_id": eid, "event_type": "subscription.canceled", "occurred_at": "2026-08-30T00:00:00Z",
        "data": {"id": sub_id},
    }).encode()
    r = requests.post(f"{LOCAL}/api/webhook/paddle", data=body, headers=_sign(body))
    assert r.status_code == 200
    ws = mongo.workspaces.find_one({"workspace_id": WS_ID})
    assert ws["plan"] == "free"
    assert ws.get("subscription_status") == "canceled"
    mongo.paddle_events.delete_one({"_id": eid})
    mongo.workspaces.update_one({"workspace_id": WS_ID}, {"$set": {"plan": "free"}, "$unset": {"paddle_subscription_id": ""}})


def test_webhook_past_due_sets_status(mongo):
    sub_id = "sub_pastdue_test"
    mongo.workspaces.update_one(
        {"workspace_id": WS_ID},
        {"$set": {"plan": "pro", "paddle_subscription_id": sub_id, "subscription_status": "active"}},
    )
    eid = f"evt_{uuid.uuid4().hex[:10]}"
    body = json.dumps({
        "event_id": eid, "event_type": "subscription.past_due", "occurred_at": "2026-08-30T00:00:00Z",
        "data": {"id": sub_id},
    }).encode()
    r = requests.post(f"{LOCAL}/api/webhook/paddle", data=body, headers=_sign(body))
    assert r.status_code == 200
    ws = mongo.workspaces.find_one({"workspace_id": WS_ID})
    assert ws.get("subscription_status") == "past_due"
    mongo.paddle_events.delete_one({"_id": eid})
    mongo.workspaces.update_one(
        {"workspace_id": WS_ID},
        {"$set": {"plan": "free", "subscription_status": "active"}, "$unset": {"paddle_subscription_id": ""}},
    )


def test_portal_requires_billing_manage():
    r = requests.post(f"{BASE_URL}/api/payments/paddle/portal", headers=_h(MEMBER_TOKEN))
    assert r.status_code == 403


def test_portal_requires_customer(mongo):
    mongo.workspaces.update_one({"workspace_id": WS_ID}, {"$unset": {"paddle_customer_id": ""}})
    r = requests.post(f"{BASE_URL}/api/payments/paddle/portal", headers=_h(OWNER_TOKEN))
    assert r.status_code == 400
