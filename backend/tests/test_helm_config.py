"""Tests for helm_config URL helpers."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import helm_config  # noqa: E402


def test_registrable_cookie_domain_strips_www():
    assert helm_config.registrable_cookie_domain("www.trenston.com") == "trenston.com"


def test_registrable_cookie_domain_apex():
    assert helm_config.registrable_cookie_domain("trenston.com") == "trenston.com"


def test_public_api_origin_defaults_to_canonical():
    assert helm_config.public_api_origin().startswith("https://www.trenston.com")


def test_is_stale_deploy_url():
    assert helm_config.is_stale_deploy_url("https://helm-company-cockpit.onrender.com")
    assert helm_config.is_stale_deploy_url("https://foo.vercel.app")
    assert not helm_config.is_stale_deploy_url("https://www.trenston.com")
