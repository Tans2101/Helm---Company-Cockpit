"""POST /api/internal/run-retention-checks for the Render cron job (stdlib only)."""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

URL = (os.environ.get("RETENTION_CRON_URL") or "").strip()
SECRET = (os.environ.get("INTERNAL_CRON_SECRET") or "").strip()


def main() -> int:
    if not URL:
        print("RETENTION_CRON_URL is not set", file=sys.stderr)
        return 1
    if not SECRET:
        print("INTERNAL_CRON_SECRET is not set", file=sys.stderr)
        return 1
    req = urllib.request.Request(
        URL,
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Trenston-Cron-Secret": SECRET,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(body)
            return 0 if 200 <= resp.status < 300 else 1
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
