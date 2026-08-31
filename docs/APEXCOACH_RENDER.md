# Put Helm on apexcoach.tech (replace Kalun on Render)

Kalun is still live at **apexcoach.tech** on Render service `apex-v4-jjbo`.  
Helm can take over **without changing DNS** — same domain, same Render service, new GitHub repo.

## What you do in Render (~5 minutes)

1. Open [Render Dashboard](https://dashboard.render.com) → service **apex-v4-jjbo** (or whatever has `apexcoach.tech`)
2. **Settings → Build & Deploy**
   - **Repository:** `Tans2101/Helm---Company-Cockpit`
   - **Branch:** `main`
   - **Root Directory:** *(leave blank)*
   - **Build Command:** `bash scripts/render-apexcoach-build.sh`
   - **Start Command:** `cd backend && uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/health`
3. **Environment** — set or update:

| Key | Value |
|-----|--------|
| `HELM_SERVE_STATIC` | `true` |
| `FRONTEND_URL` | `https://apexcoach.tech` |
| `APP_URL` | `https://apexcoach.tech` |
| `CORS_ORIGINS` | `https://apexcoach.tech,https://www.apexcoach.tech` |
| `USE_ATLAS_MONGO` | `true` |
| `MONGO_URL` | your Atlas URI |
| `DB_NAME` | `helm` |
| `CLERK_SECRET_KEY` | from Clerk (apexcoach instance) |
| `CLERK_PUBLISHABLE_KEY` | matching `pk_live_...` |
| `REACT_APP_CLERK_PUBLISHABLE_KEY` | same `pk_live_...` (used at build time) |
| `CLERK_JWKS_URL` | e.g. `https://clerk.apexcoach.tech/.well-known/jwks.json` |
| `REACT_APP_HELM_ORIGIN` | `https://apexcoach.tech` |

4. **Manual Deploy** → wait for build (~5–8 min; installs Node + Python + builds React)

5. After deploy:
   ```bash
   curl -X POST https://apexcoach.tech/api/setup/clerk-sync
   ```

6. Open **https://apexcoach.tech/login**

## What the build does

`scripts/render-apexcoach-build.sh`:

1. `npm ci` + `npm run build` in `frontend/`
2. Copies `frontend/build` → `backend/static`
3. `pip install -r requirements-prod.txt`

FastAPI serves the React app **and** `/api/*` on the same origin — no Vercel required for apexcoach.tech.

## Clerk Dashboard

- **Account Portal → Redirects:** `https://apexcoach.tech/app`
- **Developers → Allowed origins:** `https://apexcoach.tech`

## Optional cleanup

- Suspend old **helm-company-cockpit** Render service if you no longer need the separate API URL
- Vercel project can stay as a backup preview URL
