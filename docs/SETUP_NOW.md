# Helm production setup — helmcontrol.online

**Live app:** https://www.helmcontrol.online  
**API (proxied):** https://www.helmcontrol.online/api/* → Render

---

## Architecture

| Layer | Service |
|-------|---------|
| Domain registrar | Namecheap |
| Website | Vercel (`frontend/`) |
| API | Render (`backend/`, service `helm-company-cockpit`) |
| Auth | Clerk (`clerk.helmcontrol.online`) |
| Database | MongoDB Atlas |

---

## Step 1 — Render env vars

Render → **helm-company-cockpit** → **Environment**:

| Variable | Value |
|----------|-------|
| `FRONTEND_URL` | `https://www.helmcontrol.online` |
| `APP_URL` | `https://www.helmcontrol.online` |
| `CORS_ORIGINS` | `https://www.helmcontrol.online,https://helmcontrol.online` |
| `COOKIE_DOMAIN` | `helmcontrol.online` |
| `CLERK_SECRET_KEY` | `sk_live_...` from Clerk API Keys |
| `CLERK_PUBLISHABLE_KEY` | `pk_live_Y2xlcmsuaGVsbWNvbnRyb2wub25saW5lJA` (or from Clerk) |
| `CLERK_JWKS_URL` | `https://clerk.helmcontrol.online/.well-known/jwks.json` |
| `CLERK_PRIMARY_ORIGIN` | `https://www.helmcontrol.online` |
| `SETUP_SECRET` | auto-generated (for `/api/setup/clerk-sync`) |

Verify: https://www.helmcontrol.online/api/auth/config → `clerk_enabled: true`, `clerk_keys_aligned: true`

---

## Step 2 — Vercel

1. Project **helm-company-cockpit** → Root Directory = `frontend`
2. Domains: `helmcontrol.online`, `www.helmcontrol.online`
3. Redeploy after merges to `main`

`vercel.json` rewrites `/api/*` to Render.

---

## Step 3 — Clerk Dashboard

| Area | Setting |
|------|---------|
| **Account Portal → Redirects** | All after sign-in / sign-up URLs → **`https://www.helmcontrol.online/app`** |
| **Developers** → Allowed origins | `https://www.helmcontrol.online`, `https://helmcontrol.online`, `http://localhost:3000` |

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

1. https://www.helmcontrol.online/login
2. Sign up / sign in (Google or email)
3. Land on https://www.helmcontrol.online/app

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Sign-up button does nothing | Redeploy Render + Vercel; check `/api/auth/config` for `clerk_keys_aligned: true` |
| Clerk shows apexcoach | Expected until Clerk primary domain is changed; redirects must point to helmcontrol |
| Login loops | Set `COOKIE_DOMAIN=helmcontrol.online` on Render |
| API JSON on wrong URL | Use `www.helmcontrol.online`, not `onrender.com` directly |
