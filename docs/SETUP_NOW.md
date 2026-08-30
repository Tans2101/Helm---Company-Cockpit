# Helm — set up NOW (your deployment)

**Your API:** `https://helm-company-cockpit.onrender.com`  
**Your app:** `https://helm-company-cockpit.vercel.app` — use `/login` to sign in

**Current status (check anytime):**
- Clerk: https://helm-company-cockpit.onrender.com/api/auth/config → `"clerk_enabled": true` ✓
- Mongo: https://helm-company-cockpit.onrender.com/api/health → needs `"mongo": true`

---

## Step 1 — Database (pick one)

### Option A — Render Blueprint (recommended, no Atlas)

1. Render Dashboard → **Blueprints** → **New Blueprint Instance**
2. Connect repo `Tans2101/Helm---Company-Cockpit` → sync `render.yaml`
3. This provisions **helm-mongo** (private Mongo) + **helm-company-cockpit** (API)
4. On the web service, add Clerk + Anthropic keys (Step 2 below)
5. **Delete** any broken `MONGO_URL` env var unless you use Atlas (Option B)

**Done when:** `/api/setup/status` shows `"mongo": true` and `"mongo_source": "render_pserv"`

### Option B — MongoDB Atlas

1. https://cloud.mongodb.com → create free cluster
2. **Database Access** → user + password (save password)
3. **Network Access** → **Allow Access from Anywhere** (`0.0.0.0/0`)
4. **Database** → **Connect** → **Drivers** → **Python** → copy connection string  
   Looks like: `mongodb+srv://helm_user:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
5. Replace `<password>` with your real password
6. On Render set `USE_ATLAS_MONGO=true` and paste the URI as `MONGO_URL`

---

## Step 2 — Render env vars (~2 min)

Render → **helm-company-cockpit** → **Environment** → add/update:

| Key | Value |
|-----|--------|
| `MONGO_URL` | paste Atlas connection string |
| `DB_NAME` | `helm` |
| `SESSION_SECRET` | any long random string |
| `OAUTH_STATE_SECRET` | any long random string |
| `FRONTEND_URL` | `https://helm-company-cockpit.vercel.app` |
| `APP_URL` | `https://helm-company-cockpit.vercel.app` |
| `CORS_ORIGINS` | `https://helm-company-cockpit.vercel.app` |
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `lax` |
| `CLERK_SECRET_KEY` | `sk_live_...` or `sk_test_...` from Clerk |
| `CLERK_PUBLISHABLE_KEY` | matching `pk_live_...` or `pk_test_...` (**must match secret**) |
| `CLERK_JWKS_URL` | `https://causal-caribou-2352.clerk.accounts.dev/.well-known/jwks.json` |

> Keys must be from the **same** Clerk environment (both Development or both Production). Check https://helm-company-cockpit.onrender.com/api/auth/config → `clerk_secret_mode` should match your publishable key (`pk_test` ↔ `sk_test`, `pk_live` ↔ `sk_live`).

**Save** → **Manual Deploy** (wait ~2 min)

Test: https://helm-company-cockpit.onrender.com/api/health → `"mongo": true`

---

## Step 3 — Vercel (~1 min)

Vercel → Project → **Environment Variables**:

| Key | Value |
|-----|--------|
| `REACT_APP_CLERK_PUBLISHABLE_KEY` | `pk_live_...` from Clerk |

**Redeploy** Vercel.

`vercel.json` already points API to Render — no change needed.

---

## Step 4 — Clerk (~1 min)

Clerk Dashboard (Live mode) → **Configure** → **Domains** → add your **Vercel URL**

---

## Step 5 — Test Helm

1. Open `https://YOUR-VERCEL-URL/login`
2. Sign in with Google / Microsoft / email (Clerk)
3. Create a company
4. Sign out → sign in again → **same company**

---

## Optional later

| Key | Where | For |
|-----|--------|-----|
| `ANTHROPIC_API_KEY` | Render | Ask Helm AI |
| `PADDLE_*` | Render | Pro billing |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Render shows JSON / pretty-print | Wrong URL — use **Vercel**, not Render |
| `mongo: false` | Check https://helm-company-cockpit.onrender.com/api/setup/status → `mongo_probes`. Sync **render.yaml** blueprint (helm-mongo) **or** fix Atlas `MONGO_URL` + `USE_ATLAS_MONGO=true` |
| Login loops | Set `FRONTEND_URL` / `CORS_ORIGINS` on Render |
| Clerk error | Add Vercel URL in Clerk Domains + redeploy Vercel |
