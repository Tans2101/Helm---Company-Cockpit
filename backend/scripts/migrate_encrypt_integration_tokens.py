#!/usr/bin/env python3
"""One-time migration: seal plaintext google_tokens / quickbooks_tokens at rest.

Run from backend/ (or with PYTHONPATH=backend) after INTEGRATION_ENCRYPTION_KEY is set:

  cd backend
  INTEGRATION_ENCRYPTION_KEY=... MONGO_URL=... DB_NAME=helm \\
    python scripts/migrate_encrypt_integration_tokens.py

Safe to re-run: already-sealed blobs are skipped. Does not revoke or reconnect
integrations — only rewrites the stored credential shape.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from pymongo import MongoClient

import credential_crypto as crypto

TOKEN_FIELDS = ("google_tokens", "quickbooks_tokens")


def main() -> int:
    mongo_url = (os.environ.get("MONGO_URL") or "").strip()
    if not mongo_url:
        host = (os.environ.get("MONGO_HOST") or "").strip()
        port = (os.environ.get("MONGO_PORT") or "27017").strip()
        if host:
            mongo_url = f"mongodb://{host}:{port}"
    if not mongo_url:
        print("MONGO_URL (or MONGO_HOST) is required", file=sys.stderr)
        return 1

    db_name = (os.environ.get("DB_NAME") or "helm").strip()
    # Touch key early so misconfig fails before any writes.
    try:
        crypto.encrypt_credential("probe")
    except crypto.CredentialCryptoError as exc:
        print(f"Encryption key error: {exc}", file=sys.stderr)
        return 1

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[db_name]
    scanned = 0
    updated = 0
    skipped = 0
    errors = 0

    cursor = db.workspaces.find(
        {"$or": [{f: {"$type": "object"}} for f in TOKEN_FIELDS]},
        {"_id": 1, "workspace_id": 1, **{f: 1 for f in TOKEN_FIELDS}},
    )
    for doc in cursor:
        scanned += 1
        ws_id = doc.get("workspace_id") or str(doc.get("_id"))
        patch: dict = {}
        for field in TOKEN_FIELDS:
            raw = doc.get(field)
            if not raw:
                continue
            if crypto.is_sealed_credentials(raw):
                skipped += 1
                continue
            if not crypto.needs_reencryption(raw):
                continue
            try:
                sealed = crypto.seal_credentials(raw)
            except Exception as exc:
                errors += 1
                print(f"FAIL {ws_id} {field}: {exc}", file=sys.stderr)
                continue
            if sealed is None:
                continue
            # Round-trip check before writing.
            opened = crypto.unseal_credentials(sealed)
            if not opened or opened.get("access_token") != raw.get("access_token"):
                # QuickBooks may use different shapes; compare full JSON keys at least.
                if opened != raw:
                    errors += 1
                    print(f"FAIL {ws_id} {field}: round-trip mismatch", file=sys.stderr)
                    continue
            patch[field] = sealed
        if patch:
            db.workspaces.update_one({"_id": doc["_id"]}, {"$set": patch})
            updated += 1
            print(f"sealed {ws_id}: {', '.join(patch.keys())}")

    print(
        f"done scanned={scanned} workspaces_updated={updated} "
        f"already_sealed_fields={skipped} errors={errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
