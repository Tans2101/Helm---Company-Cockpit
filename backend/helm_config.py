"""Canonical Helm URLs — single source of truth for production domain."""
from __future__ import annotations

import os

HELM_CANONICAL_ORIGIN = os.environ.get(
    "HELM_CANONICAL_ORIGIN", "https://helmcontrol.online"
).strip().rstrip("/")

# Preferred custom domains (first match wins in clerk_auth.primary_frontend_origin).
HELM_PRIMARY_HOSTS = ("helmcontrol.online", "apexcoach.tech")
