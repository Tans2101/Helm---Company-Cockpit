#!/usr/bin/env bash
# Build Helm for apexcoach.tech on a single Render web service (replaces Kalun).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Installing frontend dependencies"
cd "$ROOT/frontend"
npm ci

echo "==> Building React app for apexcoach.tech"
export REACT_APP_HELM_ORIGIN="${REACT_APP_HELM_ORIGIN:-https://helmcontrol.online}"
export REACT_APP_CLERK_SIGN_IN_FORCE_REDIRECT_URL="${REACT_APP_CLERK_SIGN_IN_FORCE_REDIRECT_URL:-https://helmcontrol.online/app}"
export REACT_APP_CLERK_SIGN_UP_FORCE_REDIRECT_URL="${REACT_APP_CLERK_SIGN_UP_FORCE_REDIRECT_URL:-https://helmcontrol.online/app}"
export REACT_APP_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL="${REACT_APP_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL:-https://helmcontrol.online/app}"
export REACT_APP_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL="${REACT_APP_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL:-https://helmcontrol.online/app}"
npm run build

echo "==> Copying build to backend/static"
rm -rf "$ROOT/backend/static"
cp -r build "$ROOT/backend/static"

echo "==> Installing Python dependencies"
cd "$ROOT/backend"
pip install --upgrade pip
pip install -r requirements-prod.txt

echo "==> apexcoach build complete"
