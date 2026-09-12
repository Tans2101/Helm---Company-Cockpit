#!/usr/bin/env bash
# Per-boot runtime init: ensure a local MongoDB is running and ready.
# Idempotent — safe to run on every environment start.
set -euo pipefail

MONGO_DIR="$HOME/.helm-mongo"
DATA_DIR="$MONGO_DIR/data"
LOG_FILE="$MONGO_DIR/mongod.log"
mkdir -p "$DATA_DIR"

is_up() {
  mongosh --quiet --host 127.0.0.1 --port 27017 --eval 'db.runCommand({ping:1})' >/dev/null 2>&1
}

if is_up; then
  echo "mongod already running."
  exit 0
fi

# Clean up a stale lock from a previous boot before starting.
rm -f "$DATA_DIR/mongod.lock" 2>/dev/null || true

mongod --dbpath "$DATA_DIR" --bind_ip 127.0.0.1 --port 27017 \
  --fork --logpath "$LOG_FILE"

for _ in $(seq 1 30); do
  if is_up; then
    echo "mongod ready on 127.0.0.1:27017."
    exit 0
  fi
  sleep 1
done

echo "ERROR: mongod did not become ready in time." >&2
tail -n 20 "$LOG_FILE" >&2 || true
exit 1
