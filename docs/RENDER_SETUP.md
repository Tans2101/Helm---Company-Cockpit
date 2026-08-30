# Render deploy — if build fails, use these exact settings

## Web Service settings

| Field | Value |
|-------|--------|
| **Repository** | `Tans2101/Helm---Company-Cockpit` |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements-prod.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/api/health` |

## After repo transfer to Tans2101

Render may still point at the old `tansherd21` repo. Fix:

1. Render Dashboard → your service → **Settings**
2. **Build & Deploy** → **Repository** → **Connect** / change to `Tans2101/Helm---Company-Cockpit`
3. Or: Account → **GitHub** → configure access for **Tans2101** org/user
4. **Manual Deploy** → Deploy latest commit

## "Build upload failed"

Usually **not** your code — upload to Render’s builders failed. Try in order:

1. **Manual Deploy** again (transient network blip)
2. Reconnect **GitHub** on Render (especially after transfer to Tans2101)
3. Confirm **Root Directory** = `backend` (not empty, not `frontend`)
4. Confirm branch = `main`
5. Check https://status.render.com

## Minimum env vars before first deploy

**Recommended:** deploy via **Blueprint** (`render.yaml` in repo root) so `helm-mongo` and `MONGO_HOSTPORT` are wired automatically.

If you created the web service manually, either:

1. **Blueprint sync** — Render → Blueprints → New Instance → this repo, or  
2. **Atlas** — set `USE_ATLAS_MONGO=true` and a valid `MONGO_URL`

| Key | Required for build? | Required for run? |
|-----|---------------------|-------------------|
| `MONGO_URL` or `MONGO_HOST` / blueprint | No | **Yes** (one of) |
| `DB_NAME` | No | Yes (`helm`) |
| `SESSION_SECRET` | No | Yes |
| `CLERK_SECRET_KEY` + `CLERK_JWKS_URL` | No | Yes (for login) |

Check: https://helm-company-cockpit.onrender.com/api/setup/status — `mongo_probes` shows which URLs were tried.
