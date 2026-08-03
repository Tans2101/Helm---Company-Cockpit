# Helm — CEO Operating System

Helm is a multi-tenant executive cockpit for seed/Series A startups: morning briefing, decisions, financials, pipeline, team bandwidth, and Ask Helm AI.

## Go-live checklist

Before deploying to production, verify:

1. **Secrets** — Set strong `SESSION_SECRET` and `OAUTH_STATE_SECRET`; never commit real `.env` files.
2. **Security defaults** — `ALLOW_DEMO_LOGIN=false`, `DEMO_RESET_ENABLED=false`, `COOKIE_SECURE=true` behind HTTPS.
3. **URLs** — Set `FRONTEND_URL`, `APP_URL`, and `CORS_ORIGINS` to your production domain(s).
4. **MongoDB** — Provision a managed cluster; confirm `/api/health` returns `mongo: true`.
5. **Paddle** — Configure live `PADDLE_*` keys, webhook URL (`/api/webhook/paddle`), and `PRO_PRICE`.
6. **Google auth** — Emergent OAuth redirect must point to your production `/app` route.
7. **Email** — Set `RESEND_API_KEY` and verified `SENDER_EMAIL` for team invites.
8. **GDPR** — Confirm `/api/account/export` and delete flows meet your policy; link `/privacy` and `/terms`.
9. **Smoke test** — Login → create/join workspace → billing portal → briefing → decisions CRUD.

## Local development

Google “Continue with Google” uses **Emergent’s hosted OAuth** (`auth.emergentagent.com`). That loop only works on Emergent previews. For localhost, enable demo login:

```bash
# Backend
cd backend
cp .env.example .env
# Required for local sign-in without Emergent:
#   ALLOW_DEMO_LOGIN=true
#   MONGO_URL=mongodb://localhost:27017
#   DB_NAME=helm
#   SESSION_SECRET=dev-secret
#   FRONTEND_URL=http://localhost:3000
#   CORS_ORIGINS=http://localhost:3000
#   APP_URL=http://localhost:3000
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend
cd frontend
echo 'REACT_APP_BACKEND_URL=http://localhost:8001' > .env
yarn install
yarn start
```

Open http://localhost:3000/login and use **Enter as demo founder**.

## API overview

- Auth: `/api/auth/session`, `/api/auth/me`, `/api/auth/logout`
- Billing: Paddle checkout via `/api/billing/paddle/config`; portal at `/api/payments/paddle/portal`
- Health: `/api/health`

See `backend/.env.example` for all environment variables.
