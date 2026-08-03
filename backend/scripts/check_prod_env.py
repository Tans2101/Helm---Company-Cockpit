#!/usr/bin/env python3
"""Fail fast if critical production env vars are missing. Run on Render build or locally."""
from __future__ import annotations

import os
import sys

REQUIRED = [
    "MONGO_URL",
    "DB_NAME",
    "SESSION_SECRET",
    "FRONTEND_URL",
    "APP_URL",
    "CORS_ORIGINS",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
]

RECOMMENDED = [
    "PADDLE_API_KEY",
    "PADDLE_CLIENT_TOKEN",
    "PADDLE_PRICE_ID",
    "PADDLE_WEBHOOK_SECRET",
    "RESEND_API_KEY",
    "SENDER_EMAIL",
]


def main() -> int:
    missing = [k for k in REQUIRED if not (os.environ.get(k) or "").strip()]
    weak = []
    if os.environ.get("SESSION_SECRET", "").strip() in ("", "change-me-in-production", "change-me-to-a-long-random-string"):
        weak.append("SESSION_SECRET looks like a placeholder")
    if os.environ.get("ALLOW_DEMO_LOGIN", "false").lower() in ("1", "true", "yes"):
        weak.append("ALLOW_DEMO_LOGIN is enabled (should be false in production)")
    if os.environ.get("COOKIE_SECURE", "false").lower() not in ("1", "true", "yes"):
        weak.append("COOKIE_SECURE should be true behind HTTPS")

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
