"""Shared helpers for Helm backend integration tests."""
import os

import pymongo


def mongo_db():
    client = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "test_database")]


def workspace_id_for(session, base_url: str) -> str:
    return session.get(f"{base_url}/api/auth/me").json()["workspace_id"]


def set_workspace_plan(session, base_url: str, plan: str) -> None:
    ws = workspace_id_for(session, base_url)
    mongo_db().workspaces.update_one({"workspace_id": ws}, {"$set": {"plan": plan}})
