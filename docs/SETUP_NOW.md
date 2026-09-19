# Trenston production setup — trenston.com

**Live app:** https://www.trenston.com  
**API (proxied):** https://www.trenston.com/api/* → Render

---

## Architecture

| Layer | Service |
|-------|---------|
| Domain registrar | Namecheap |
| Website | Vercel (`frontend/`) |
| API | Render (`backend/`, service `helm-company-cockpit`) |
| Auth | Clerk (`clerk.trenston.com`) |
| Database | MongoDB Atlas |

---

## Step 1 — Render env vars

Render → **helm-company-cockpit** → **Environment**:

| Variable | Value |
|----------|-------|
| `FRONTEND_URL` | `https://www.trenston.com` |
| `APP_URL` | `https://www.trenston.com` |
| `CORS_ORIGINS` | `https://www.trenston.com,https://trenston.com` |
| `COOKIE_DOMAIN` | `trenston.com` |
| `CLERK_SECRET_KEY` | `sk_live_...` from Clerk API Keys |
| `CLERK_PUBLISHABLE_KEY` | `pk_live_Y2xlcmsudHJlbnN0b24uY29tJA` (or from Clerk → API keys for `clerk.trenston.com`) |
| `CLERK_JWKS_URL` | `https://clerk.trenston.com/.well-known/jwks.json` |
| `CLERK_PRIMARY_ORIGIN` | `https://www.trenston.com` |
| `SETUP_SECRET` | auto-generated (for `/api/setup/clerk-sync`) |

Verify: https://www.trenston.com/api/auth/config → `clerk_enabled: true`, `clerk_keys_aligned: true`

---

## Step 2 — Vercel

1. Project **helm-company-cockpit** → Root Directory = `frontend`
2. Domains: `trenston.com`, `www.trenston.com`
3. Redeploy after merges to `main`

`vercel.json` rewrites `/api/*` to Render.

---

## Step 3 — Clerk Dashboard

| Area | Setting |
|------|---------|
| **Account Portal → Redirects** | All after sign-in / sign-up URLs → **`https://www.trenston.com/app`** |
| **Developers** → Allowed origins | `https://www.trenston.com`, `https://trenston.com`, `http://localhost:3000` |

Sync origins (after deploy sets `SETUP_SECRET`):

```bash
curl -X POST https://helm-company-cockpit.onrender.com/api/setup/clerk-sync \
  -H "X-Setup-Secret: YOUR_SETUP_SECRET"
```

---

## Step 4 — Namecheap DNS

| Type | Host | Value |
|------|------|-------|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

---

## Smoke test

1. https://www.trenston.com/login
2. Sign up / sign in (Google or email)
3. Land on https://www.trenston.com/app
4. After R2 is configured ([docs/R2_SETUP.md](R2_SETUP.md)): Financials → Upload a bill

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Sign-up button does nothing | Redeploy Render + Vercel; check `/api/auth/config` for `clerk_keys_aligned: true` |
| Clerk shows wrong domain | Confirm instance is `clerk.trenston.com`; Account Portal redirects → `https://www.trenston.com/app` |
| Login loops | Set `COOKIE_DOMAIN=trenston.com` on Render |
| API JSON on wrong URL | Use `www.trenston.com`, not `onrender.com` directly |
| Bill upload → storage not configured | Set R2 env on Render per [R2_SETUP.md](R2_SETUP.md) and redeploy |
