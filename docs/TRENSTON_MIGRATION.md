# Trenston migration checklist (Helm Control → trenston.com)

Code on `main` now targets **Trenston** at `www.trenston.com`. CSS utilities still use the internal `helm-*` prefix (implementation detail only).

Zero customers today — still treat this as a cutover sequence. **Do not expect login or OAuth to work until the dashboard steps below are done.**

## Block production until these are done

### 1. DNS (Namecheap → Vercel / Render)
- [ ] Point `trenston.com` and `www.trenston.com` to Vercel (frontend)
- [ ] Add `clerk.trenston.com` CNAME per Clerk’s instructions (after Clerk domain is created)
- [ ] Confirm API stays on Render (`helm-company-cockpit.onrender.com`) with Vercel `/api` rewrite (unchanged service name is fine)

### 2. Clerk (required before auth works)
- [ ] Create or repoint a Clerk application for **`clerk.trenston.com`**
- [ ] Add allowed origins / redirect URLs for `https://www.trenston.com` and `https://trenston.com` (`/login`, `/sign-up`, `/app`, `/auth/callback`, etc.)
- [ ] Copy **new** `pk_live_…` and `sk_live_…` from Clerk
- [ ] Set them in **Vercel** (`REACT_APP_CLERK_PUBLISHABLE_KEY`) and **Render** (`CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL=https://clerk.trenston.com/.well-known/jwks.json`)
- [ ] Verify a bare login on `www.trenston.com` before wiring integrations
- Repo currently commits a *derived* publishable key for `clerk.trenston.com` — replace with the real key from the Clerk dashboard

### 3. Vercel project
- [ ] Attach custom domains `trenston.com` + `www.trenston.com`
- [ ] Keep `helmcontrol.online` + `www.helmcontrol.online` attached so the 301s in `frontend/vercel.json` fire
- [ ] Env: `REACT_APP_HELM_ORIGIN=https://www.trenston.com`, new Clerk publishable key

### 4. Google Cloud OAuth (Calendar / Gmail — `GOOGLE_CLIENT_*`)
- [ ] Authorized JS origins: `https://www.trenston.com`, `https://trenston.com`
- [ ] Redirect URIs: update every `…/api/auth/google/callback` (and related) host to `www.trenston.com`
- [ ] Clerk Google SSO: add `https://clerk.trenston.com/v1/oauth_callback`

### 5. Google Workspace (email)
- [ ] Verify `trenston.com`, set MX / SPF / DKIM / DMARC
- [ ] Decide: migrate `@helmcontrol.online` mailboxes or keep as alias domain

### 6. Integration developer apps (callback host only)
- [ ] **QuickBooks** — redirect URI → `https://www.trenston.com/api/...`
- [ ] **Xero** — same
- [ ] **HubSpot** — same
- [ ] **SAP B1** — usually customer-hosted; confirm no central OAuth redirect (likely no change)

### 7. Paddle
- [ ] Add `trenston.com` / `www.trenston.com` to checkout approved domains
- [ ] Point webhook at `https://www.trenston.com/api/webhook/paddle` (or current path)

### 8. Resend
- [ ] Verify `trenston.com` for sending (does **not** inherit helmcontrol verification)
- [ ] Set `SENDER_EMAIL` (e.g. `Trenston <contact@trenston.com>`) on Render after DNS passes

### 9. Search Console
- [ ] New property for `trenston.com`; submit `https://www.trenston.com/sitemap.xml`
- [ ] Keep `helmcontrol.online` property to watch the redirect period

### 10. Manual brand follow-ups (not in code)
- [ ] Instagram `@gethelmcontrol` → new handle/bio (code currently points at `@trenston` as a placeholder)
- [ ] LinkedIn Experience entry: Helm Control → **Trenston**
- [ ] Rename GitHub repo `Tans2101/Helm---Company-Cockpit` when ready (confirm Render + Vercel git links still resolve; `render.yaml` `repo:` still lists the old name until you rename)

## Already done in the repo
- User-facing copy, titles, JSON-LD, `llms.txt`, sitemap, robots, manifest name
- Domains in `render.yaml`, `helm_config.py`, `clerk_auth.py`, `vercel.json`
- 301s: `helmcontrol.online` / `www.helmcontrol.online` → `https://www.trenston.com/...`
- Apex `trenston.com` → `www.trenston.com`
- Trenston **T** medallion favicon / PWA / OG images
- Changelog entry: “Helm Control is now Trenston”
- Internal `helm-*` Tailwind tokens left unchanged on purpose
