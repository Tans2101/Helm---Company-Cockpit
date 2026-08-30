#!/usr/bin/env python3
"""Fail fast if critical production env vars are missing. Run on Render build or locally."""
from __future__ import annotations

import os
import sys

ALWAYS_REQUIRED = [
    "DB_NAME",
    "SESSION_SECRET",
    "FRONTEND_URL",
    "APP_URL",
    "CORS_ORIGINS",
]

RECOMMENDED = [
    "ANTHROPIC_API_KEY",
    "PADDLE_API_KEY",
    "PADDLE_CLIENT_TOKEN",
    "PADDLE_PRICE_ID",
    "PADDLE_WEBHOOK_SECRET",
    "RESEND_API_KEY",
    "SENDER_EMAIL",
]


def _mongo_configured() -> bool:
    if (os.environ.get("MONGO_HOST") or "").strip():
        return True
    if (os.environ.get("MONGO_URL") or "").strip():
        return True
    return bool(os.environ.get("RENDER"))


def _auth_configured() -> bool:
    clerk = (os.environ.get("CLERK_SECRET_KEY") or "").strip() and (
        os.environ.get("CLERK_JWKS_URL") or ""
    ).strip()
    google = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip() and (
        os.environ.get("GOOGLE_CLIENT_SECRET") or ""
    ).strip()
    return bool(clerk or google)


def main() -> int:
    missing = [k for k in ALWAYS_REQUIRED if not (os.environ.get(k) or "").strip()]
    if not _mongo_configured():
        missing.append("MONGO_URL or MONGO_HOST (or Render blueprint helm-mongo)")
    if not _auth_configured():
        missing.extend(["CLERK_SECRET_KEY+CLERK_JWKS_URL or GOOGLE_CLIENT_ID+GOOGLE_CLIENT_SECRET"])

    weak = []
    if os.environ.get("SESSION_SECRET", "").strip() in ("", "change-me-in-production", "change-me-to-a-long-random-string"):
        weak.append("SESSION_SECRET looks like a placeholder")
    if os.environ.get("ALLOW_DEMO_LOGIN", "false").lower() in ("1", "true", "yes"):
        weak.append("ALLOW_DEMO_LOGIN is enabled (should be false in production)")
    if os.environ.get("COOKIE_SECURE", "false").lower() not in ("1", "true", "yes"):
        weak.append("COOKIE_SECURE should be true behind HTTPS")
    if (
        os.environ.get("USE_ATLAS_MONGO", "false").lower() not in ("1", "true", "yes")
        and (os.environ.get("MONGO_URL") or "").startswith("mongodb+srv://")
        and os.environ.get("RENDER")
    ):
        weak.append(
            "MONGO_URL is Atlas but USE_ATLAS_MONGO=false — Render will prefer helm-mongo; "
            "delete MONGO_URL if you only use the private Mongo service"
        )

    rec_missing = [k for k in RECOMMENDED if not (os.environ.get(k) or "").strip()]

    if missing:
        print("MISSING required env:", ", ".join(missing))
    if weak:
        print("WARNINGS:")
        for w in weak:
            print(" -", w)
    if rec_missing:
        print("Optional not set yet:", ", ".join(rec_missing))

    if missing:
        return 1
    print("Production env check: required keys present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
