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

```bash
# Backend
cd backend
cp .env.example .env   # fill in values
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend
cd frontend
yarn install
yarn start
```

## API overview

- Auth: `/api/auth/session`, `/api/auth/me`, `/api/auth/logout`
- Billing: Paddle checkout via `/api/billing/paddle/config`; portal at `/api/payments/paddle/portal`
- Health: `/api/health`

See `backend/.env.example` for all environment variables.
