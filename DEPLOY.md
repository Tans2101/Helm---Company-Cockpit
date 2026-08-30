# What you must do to launch Helm (I cannot do these for you)

The code on branch `cursor/helm-production-ready-2637` is set up for **your** stack:
Render (API) + Vercel (frontend/domain) + MongoDB Atlas + Google OAuth + Anthropic + Paddle.

Do these steps in order. After each step, check the “Done when” line.

---

## Start here

1. **[MongoDB Atlas](docs/ATLAS_SETUP.md)** — database (do this first)
2. **[Clerk](docs/CLERK_SETUP.md)** — Google sign-in (no Emergent, no DIY Google OAuth for login)
3. **Render** — API (see below)
4. **Vercel** — frontend + domain
5. **Anthropic** + **Paddle** keys on Render

The code on branch `cursor/helm-production-ready-2637` is set up for **your** stack:
Render (API) + Vercel (frontend) + MongoDB Atlas + Clerk + Anthropic + Paddle.

When `CLERK_SECRET_KEY` + `CLERK_JWKS_URL` are set on Render and `REACT_APP_CLERK_PUBLISHABLE_KEY` on Vercel, Helm uses **Clerk for login** automatically.

---

## 1. MongoDB Atlas

See **[docs/ATLAS_SETUP.md](docs/ATLAS_SETUP.md)** for the full walkthrough.

Quick checklist:

**Done when:** you have a URI that works from your laptop (`mongosh` or Compass).

> This is what fixed Kalun’s “new account every login” — Emergent’s DB was not durable.

---

## 2. Clerk (sign-in)

See **[docs/CLERK_SETUP.md](docs/CLERK_SETUP.md)** for the full walkthrough.

**Done when:** you have `pk_...`, `sk_...`, and JWKS URL saved.

---

## 3. Google Cloud OAuth (optional — only if NOT using Clerk)

Skip this if Clerk is configured. Clerk handles Google login for you.

1. https://console.cloud.google.com → APIs & Services → Credentials  
2. Create **OAuth client ID** → Application type **Web application**  
3. Authorized redirect URIs (add both):
   - `https://YOUR-RENDER-API.onrender.com/api/auth/google/callback`
   - `http://localhost:8001/api/auth/google/callback` (local only)
4. Copy **Client ID** and **Client Secret**

**Done when:** you have Client ID + Secret ready to paste into Render.

---

## 3. Anthropic API key

1. https://console.anthropic.com → API keys → create key  
2. Keep it for Render env as `ANTHROPIC_API_KEY`

**Done when:** you have a `sk-ant-...` key.

---

## 4. Deploy API on Render

1. https://dashboard.render.com → New → Blueprint (or Web Service)  
2. Connect GitHub repo `tansherd21/Helm---Company-Cockpit`  
3. Branch: `cursor/helm-production-ready-2637` (or merge to `main` first)  
4. If not using Blueprint:  
   - Root directory: `backend`  
   - Build: `pip install -r requirements.txt`  
   - Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`  
   - Health: `/api/health`  
5. Set environment variables (copy from `backend/.env.example`):

| Key | Value |
|-----|--------|
| `MONGO_URL` | Atlas URI from step 1 |
| `DB_NAME` | `helm` |
| `SESSION_SECRET` | long random string |
| `OAUTH_STATE_SECRET` | long random string |
| `FRONTEND_URL` | `https://YOUR-VERCEL-DOMAIN` (set after step 5, then update) |
| `APP_URL` | same as `FRONTEND_URL` |
| `CORS_ORIGINS` | same as `FRONTEND_URL` (comma-separated if multiple) |
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `lax` if using Vercel `/api` rewrite; `none` if browser calls Render directly |
| `ALLOW_DEMO_LOGIN` | `false` |
| `DEMO_RESET_ENABLED` | `false` |
| `GOOGLE_CLIENT_ID` | from step 2 |
| `GOOGLE_CLIENT_SECRET` | from step 2 |
| `ANTHROPIC_API_KEY` | from step 3 |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` |
| `PADDLE_*` | your live Paddle keys |
| `PRO_PRICE` | your price number |
| `RESEND_API_KEY` / `SENDER_EMAIL` | optional until invites |

6. Deploy → open `https://YOUR-API.onrender.com/api/health`  

**Done when:** health returns `{"status":"ok","mongo":true}`.

---

## 5. Deploy frontend on Vercel + domain

1. https://vercel.com → Import the same GitHub repo  
2. Root directory: `frontend`  
3. Framework: Create React App / leave defaults (`yarn build` / `npm run build`)  
4. Environment:  
   - Leave `REACT_APP_BACKEND_URL` **empty** if using rewrite (recommended)  
5. Edit `frontend/vercel.json` in the repo (or Vercel rewrite UI) — replace:
   `REPLACE_WITH_YOUR_RENDER_SERVICE.onrender.com`  
   with your real Render hostname from step 4  
6. Redeploy  
7. Domains → Add your domain purchased/managed in Vercel  

**Done when:** `https://your-domain/` loads the Helm landing page.

Then go back to Render and set `FRONTEND_URL`, `APP_URL`, `CORS_ORIGINS` to that domain and redeploy API.

---

## 6. Paddle webhook

In Paddle dashboard, set webhook URL to:

`https://YOUR-API.onrender.com/api/webhook/paddle`

**Done when:** a test event is accepted (or checkout completes and plan flips to Pro).

---

## 7. Smoke test (must pass before you tell anyone)

1. Open your domain → **Continue with Google**  
2. Sign in → create a company once  
3. Sign out → sign in again with the **same Google account**  
4. Confirm you land in the **same** company (not empty onboarding)  
5. Ask Helm / briefing (needs Anthropic)  
6. Billing page loads (needs Paddle)  

**Done when:** login #2 restores the same workspace.

---

## What I already did in the repo

- Removed Emergent Google auth + Emergent LLM dependency from the app path  
- First-party Google OAuth with stable identity (`google_sub` + normalized email)  
- Anthropic client (`backend/llm.py`)  
- Legal pages, GDPR export/delete, Paddle-only billing, security defaults  
- `render.yaml`, `frontend/vercel.json`, `backend/.env.example`, this file  
- Removed Emergent visual-edits package so Vercel can install without Emergent CDN  

PR: https://github.com/tansherd21/Helm---Company-Cockpit/pull/3  

---

## What I cannot do from here

- Log into your Atlas / Google Cloud / Render / Vercel / Anthropic / Paddle accounts  
- Buy or attach your domain  
- Paste your live secrets into those dashboards  
- Click Deploy on your behalf  

Those are the only remaining blockers.
