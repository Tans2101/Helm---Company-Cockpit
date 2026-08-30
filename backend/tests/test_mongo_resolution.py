"""Mongo URL candidate ordering for Render vs Atlas."""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_mongo_resolution")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import _mongo_candidate_urls  # noqa: E402


def test_prefers_render_pserv_when_atlas_not_forced(monkeypatch):
    monkeypatch.setenv("USE_ATLAS_MONGO", "false")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("MONGO_URL", "mongodb+srv://user:pass@cluster.mongodb.net/")
    monkeypatch.delenv("MONGO_HOST", raising=False)
    urls = _mongo_candidate_urls()
    assert urls[0] == "mongodb://helm-mongo:27017"
    assert urls[1].startswith("mongodb+srv://")


def test_atlas_first_when_use_atlas_true(monkeypatch):
    monkeypatch.setenv("USE_ATLAS_MONGO", "true")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("MONGO_URL", "mongodb+srv://user:pass@cluster.mongodb.net/")
    monkeypatch.delenv("MONGO_HOST", raising=False)
    urls = _mongo_candidate_urls()
    assert urls[0].startswith("mongodb+srv://")
    assert "helm-mongo" in urls[1]


def test_local_mongo_url_only(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("MONGO_HOST", raising=False)
    monkeypatch.setenv("USE_ATLAS_MONGO", "false")
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    urls = _mongo_candidate_urls()
    assert urls == ["mongodb://localhost:27017"]


def test_mongo_host_override(monkeypatch):
    monkeypatch.setenv("USE_ATLAS_MONGO", "false")
    monkeypatch.setenv("MONGO_HOST", "custom-mongo.internal")
    monkeypatch.setenv("MONGO_URL", "mongodb+srv://x/")
    urls = _mongo_candidate_urls()
    assert urls[0] == "mongodb://custom-mongo.internal:27017"
