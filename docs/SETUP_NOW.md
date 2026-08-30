# Helm — set up NOW (your deployment)

**Your API:** `https://helm-company-cockpit.onrender.com`  
**Your app:** `https://helm-company-cockpit.vercel.app` — use `/login` to sign in

**Current status (check anytime):**
- Clerk: https://helm-company-cockpit.onrender.com/api/auth/config → `"clerk_enabled": true` ✓
- Mongo: https://helm-company-cockpit.onrender.com/api/health → needs `"mongo": true`

---

## Step 1 — MongoDB Atlas (~5 min) **DO THIS FIRST**

1. https://cloud.mongodb.com → create free cluster
2. **Database Access** → user + password (save password)
3. **Network Access** → **Allow Access from Anywhere** (`0.0.0.0/0`)
4. **Database** → **Connect** → **Drivers** → **Python** → copy connection string  
   Looks like: `mongodb+srv://helm_user:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
5. Replace `<password>` with your real password

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
| `CLERK_SECRET_KEY` | `sk_live_...` from Clerk |
| `CLERK_JWKS_URL` | from Clerk API keys page |

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
| `mongo: false` | Fix `MONGO_URL` + Atlas network `0.0.0.0/0` |
| Login loops | Set `FRONTEND_URL` / `CORS_ORIGINS` on Render |
| Clerk error | Add Vercel URL in Clerk Domains + redeploy Vercel |
