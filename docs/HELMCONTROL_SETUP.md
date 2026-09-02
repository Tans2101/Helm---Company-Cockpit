# Put Helm on helmcontrol.online (Namecheap + Vercel + Render API)

**App:** https://www.helmcontrol.online  
**API:** https://helm-company-cockpit.onrender.com (proxied via Vercel `/api/*`)

## Who hosts what?

| Piece | Provider | Role |
|-------|----------|------|
| **Domain registration** | **Namecheap** | You own `helmcontrol.online` here |
| **Website (React UI)** | **Vercel** | Serves `www.helmcontrol.online` |
| **API (FastAPI)** | **Render** | `helm-company-cockpit.onrender.com` — **not** the public website |
| **DNS** | Namecheap Advanced DNS | A/CNAME records point `@` and `www` to Vercel |

The **Render deploy button** updates the **API only**. Vercel serves the site and proxies `/api/*` to Render, so users on `helmcontrol.online` hit Vercel first.

Clerk primary domain is **helmcontrol.online** (`clerk.helmcontrol.online`).

---

## Step 1 — Namecheap DNS (~3 min)

Namecheap → **Domain List** → **helmcontrol.online** → **Manage** → **Advanced DNS**

### Option A — Use Vercel nameservers (easiest)

1. Vercel → **Domains** → **Add** → `helmcontrol.online`
2. Vercel shows two nameservers (e.g. `ns1.vercel-dns.com`, `ns2.vercel-dns.com`)
3. Namecheap → **Domain** tab → **Nameservers** → **Custom DNS** → paste Vercel nameservers
4. Save (propagation can take up to 24h; often 15–30 min)

### Option B — Keep Namecheap DNS (Advanced DNS records)

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | `@` | `76.76.21.21` | Automatic |
| CNAME | `www` | `cname.vercel-dns.com` | Automatic |

Remove any parking-page records Namecheap adds by default.

---

## Step 2 — Vercel (~2 min)

1. **helm-company-cockpit** → **Settings** → **Domains** → add:
   - `helmcontrol.online`
   - `www.helmcontrol.online` (optional)
2. **Settings** → **General** → **Root Directory** = `frontend`
3. **Environment Variables**:
   - `REACT_APP_CLERK_PUBLISHABLE_KEY` = matching `pk_live_...` (same instance as Render `CLERK_SECRET_KEY`)
   - If unset, the app loads the publishable key from `/api/auth/config` after deploy (Render derives it from `CLERK_JWKS_URL`).
   - `/__clerk` proxy runs on Vercel Edge and forwards to Render (no extra Vercel secrets needed).
4. **Redeploy** production

`frontend/vercel.json` already rewrites `/api/*` to Render.

---

## Step 3 — Clerk Dashboard (~3 min)

| Area | Setting |
|------|---------|
| **Account Portal → Redirects** | Set **every** after sign-in / sign-up fallback & force URL to **`https://www.helmcontrol.online/app`** |
| **Developers** → Allowed origins | `https://www.helmcontrol.online`, `https://helmcontrol.online`, `http://localhost:3000` |
| **Domains** | CNAME below. If `clerk.helmcontrol.online` SSL is pending, Helm uses a **proxy** at `https://www.helmcontrol.online/__clerk` (set automatically via clerk-sync). |

### Clerk DNS (Namecheap Advanced DNS)

| Type | Host | Value |
|------|------|-------|
| CNAME | `clerk` | `frontend-api.clerk.services` |
| CNAME | `accounts` | `accounts.clerk.services` |

If sign-in spins forever, add apex **CAA** records (Namecheap → Advanced DNS, Host blank):

- `0 issue "pki.goog"`
- `0 issue "digicert.com"`

Keep existing `letsencrypt.org` if present. Wait 5–30 minutes after DNS changes, then **Verify** in Clerk Dashboard.

Then sync from terminal (use `SETUP_SECRET` from Render env):

```bash
curl -X POST https://helm-company-cockpit.onrender.com/api/setup/clerk-sync \
  -H "X-Setup-Secret: YOUR_SETUP_SECRET"
```

---

## Step 4 — Test

1. https://www.helmcontrol.online/login
2. Sign in with Google
3. Land on https://helmcontrol.online/app

While DNS propagates, use https://helm-company-cockpit.vercel.app/login

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Vercel "Invalid Configuration" | DNS must point to `76.76.21.21` / `cname.vercel-dns.com`, not Render |
| Login loops | `POST /api/setup/clerk-sync` after deploy |
| Page stuck on "Loading sign-in" | Redeploy Vercel + Render. Verify `GET /__clerk/v1/client` returns JSON. Run `POST /api/setup/clerk-sync` if needed. Also verify `clerk.helmcontrol.online` DNS + CAA (`pki.goog`, `digicert.com`). |
| **Google sign-in blocked — `redirect_uri_mismatch`** | In Google Cloud Console → Credentials → your Clerk Google OAuth client, add redirect URI `https://clerk.helmcontrol.online/v1/oauth_callback` and JS origins `https://helmcontrol.online`, `https://www.helmcontrol.online`, `https://clerk.helmcontrol.online`. Clerk Dashboard → SSO → Google must use **custom credentials** (production). Check: `GET /api/setup/google-oauth` on Render. |
| Clerk redirect to wrong site | Account Portal → `https://helmcontrol.online/app` |
| API errors | Check Render `/api/health` → `"mongo": true` |
