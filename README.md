# Helm — CEO Operating System

Company cockpit for founders. This repo is the source of truth — **Emergent preview is a separate deploy** and will not pick up Cursor changes unless you push and redeploy there.

## Open it here (Cursor Cloud)

While this agent is running, services are on:

| Service | URL |
|---------|-----|
| App | http://localhost:3000 |
| API | http://localhost:8000/api |

In the Cursor Agents window, use the **port-forward / plug** control to open forwarded `localhost:3000`.

1. Go to **Login**
2. Click **Enter as demo founder** (no Emergent Google auth / credits needed)
3. Create a company → pick sample or clean onboarding

## Run locally on your machine

```bash
# MongoDB on 27017
# backend/.env (gitignored) — minimum:
#   MONGO_URL=mongodb://127.0.0.1:27017
#   DB_NAME=helm
#   ALLOW_DEMO_LOGIN=true
#   COOKIE_SECURE=false
#   CORS_ORIGINS=http://localhost:3000
#   (+ Paddle keys if you want checkout)

cd backend && python3 -m uvicorn server:app --reload --port 8000

# frontend/.env
#   REACT_APP_BACKEND_URL=http://localhost:8000
cd frontend && npm install --legacy-peer-deps && npm start
```

## Deploy without Emergent

Push this branch and host API + SPA + Mongo anywhere (Railway, Render, Fly, VPS). Set the same env vars on that host. Point Paddle webhooks at `https://<your-api>/api/webhook/paddle`.

## Pricing note

Pro display price defaults to `$8` to match the current Paddle price ID; override with `PRO_PRICE` (fair launch band is still ~$99–149/mo).
