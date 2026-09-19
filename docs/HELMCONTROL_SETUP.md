# Put Trenston on trenston.com (Namecheap + Vercel + Render API)

**App:** https://www.trenston.com  
**API:** https://helm-company-cockpit.onrender.com (proxied via Vercel `/api/*`)

## Who hosts what?

| Piece | Provider | Role |
|-------|----------|------|
| **Domain registration** | **Namecheap** | You own `trenston.com` here |
| **Website (React UI)** | **Vercel** | Serves `www.trenston.com` |
| **API (FastAPI)** | **Render** | `helm-company-cockpit.onrender.com` — **not** the public website |
| **DNS** | Namecheap Advanced DNS | A/CNAME records point `@` and `www` to Vercel |

The **Render deploy button** updates the **API only**. Vercel serves the site and proxies `/api/*` to Render, so users on `trenston.com` hit Vercel first.

Clerk primary domain is **trenston.com** (`clerk.trenston.com`).

---

## Step 1 — Namecheap DNS (~3 min)

Namecheap → **Domain List** → **trenston.com** → **Manage** → **Advanced DNS**

### Option A — Use Vercel nameservers (easiest)

1. Vercel → **Domains** → **Add** → `trenston.com`
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
   - `trenston.com`
   - `www.trenston.com` (optional)
2. **Settings** → **General** → **Root Directory** = `frontend`
3. **Environment Variables**:
   - `REACT_APP_CLERK_PUBLISHABLE_KEY` = matching `pk_live_...` (same instance as Render `CLERK_SECRET_KEY`)
   - `CLERK_SECRET_KEY` = matching `sk_live_...`, stored as a protected Vercel secret (never in `vercel.json`)
   - If unset, the app loads the publishable key from `/api/auth/config` after deploy (Render derives it from `CLERK_JWKS_URL`).
   - `/__clerk` proxies directly from Vercel Edge to Clerk. Render never exposes its Clerk secret.
4. **Redeploy** production

`frontend/vercel.json` already rewrites `/api/*` to Render.

---

## Step 3 — Clerk Dashboard (~3 min)

| Area | Setting |
|------|---------|
| **Account Portal → Redirects** | Set **every** after sign-in / sign-up fallback & force URL to **`https://www.trenston.com/app`** |
| **Developers** → Allowed origins | `https://www.trenston.com`, `https://trenston.com`, `http://localhost:3000` |
| **Domains** | CNAME below. If `clerk.trenston.com` SSL is pending, Trenston uses a **proxy** at `https://www.trenston.com/__clerk` (set automatically via clerk-sync). |

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

1. https://www.trenston.com/login
2. Sign in with Google
3. Land on https://trenston.com/app

While DNS propagates, use https://helm-company-cockpit.vercel.app/login

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Vercel "Invalid Configuration" | DNS must point to `76.76.21.21` / `cname.vercel-dns.com`, not Render |
| Login loops | `POST /api/setup/clerk-sync` after deploy |
| Page stuck on "Loading sign-in" | Redeploy Vercel + Render. Verify `GET /__clerk/v1/client` returns JSON. Run `POST /api/setup/clerk-sync` if needed. Also verify `clerk.trenston.com` DNS + CAA (`pki.goog`, `digicert.com`). |
| **Google sign-in blocked — `redirect_uri_mismatch`** | In Google Cloud Console → Credentials → the OAuth client used in Clerk → SSO → Google, add **both** `https://clerk.trenston.com/v1/oauth_callback` and `https://accounts.trenston.com/v1/oauth_callback`. JS origins: `https://trenston.com`, `https://www.trenston.com`, `https://clerk.trenston.com`, `https://accounts.trenston.com`. Wait 1–5 min after saving. |
| Clerk redirect to wrong site | Account Portal → `https://trenston.com/app` |
| API errors | Check Render `/api/health` → `"mongo": true` |
