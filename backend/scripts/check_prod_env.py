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

    sk = (os.environ.get("CLERK_SECRET_KEY") or "").strip()
    pk = (os.environ.get("CLERK_PUBLISHABLE_KEY") or "").strip()
    if sk and pk:
        sk_live = sk.startswith("sk_live_")
        sk_test = sk.startswith("sk_test_")
        pk_live = pk.startswith("pk_live_")
        pk_test = pk.startswith("pk_test_")
        if (sk_live and not pk_live) or (sk_test and not pk_test):
            weak.append(
                "CLERK_SECRET_KEY mode does not match CLERK_PUBLISHABLE_KEY "
                "(use sk_live_ + pk_live_ from the same Clerk instance)"
            )
    elif sk and not pk:
        weak.append("CLERK_PUBLISHABLE_KEY unset — Render will derive from CLERK_JWKS_URL at runtime")
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
