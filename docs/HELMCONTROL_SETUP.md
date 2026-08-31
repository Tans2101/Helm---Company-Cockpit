# Put Helm on helmcontrol.online (Namecheap + Vercel + Render API)

**App:** https://helmcontrol.online  
**API:** https://helm-company-cockpit.onrender.com (proxied via Vercel `/api/*`)

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
3. **Environment Variables** (if not set):
   - `REACT_APP_CLERK_PUBLISHABLE_KEY` = your `pk_live_...`
4. **Redeploy** production

`frontend/vercel.json` already rewrites `/api/*` to Render.

---

## Step 3 — Clerk (~2 min)

Clerk Dashboard → **Configure**:

| Area | Setting |
|------|---------|
| **Domains** | Add `helmcontrol.online` |
| **Developers** → Allowed origins | `https://helmcontrol.online`, `http://localhost:3000` |
| **Account Portal → Redirects** | Set **every** fallback/force field to `https://www.helmcontrol.online/app` |
| **SSO connections** → Google | Add helmcontrol.online redirect URIs if prompted |

Then sync from terminal:

```bash
curl -X POST https://helm-company-cockpit.onrender.com/api/setup/clerk-sync
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
| Clerk redirect to wrong site | Account Portal → `https://helmcontrol.online/app` |
| API errors | Check Render `/api/health` → `"mongo": true` |
