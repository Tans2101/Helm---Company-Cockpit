# Clerk — step-by-step for Helm sign-in

Clerk handles **Google sign-in and sessions** so you don’t need Emergent or hand-rolled Google OAuth for login.

Helm still uses **MongoDB Atlas** for all company data. Clerk only replaces the **login door**.

---

## Step 1 — Create a Clerk application

1. Go to **https://clerk.com** and sign up / log in
2. **Create application**
3. Name: **Helm**
4. When asked how users sign in, enable **Google** (and Email if you want)
5. Finish setup — you land in the Clerk Dashboard

---

## Step 2 — Copy API keys

In Clerk Dashboard → **Configure** → **API keys**:

| Key | Where it goes |
|-----|----------------|
| **Publishable key** (`pk_test_...` or `pk_live_...`) | Vercel: `REACT_APP_CLERK_PUBLISHABLE_KEY` |
| **Secret key** (`sk_test_...` or `sk_live_...`) | Render: `CLERK_SECRET_KEY` |

Never commit these to git.

---

## Step 3 — Copy JWKS URL

Still in **API keys**, find **JWKS URL** (or **Frontend API** URL).

It looks like:

```text
https://verb-noun-00.clerk.accounts.dev/.well-known/jwks.json
```

Add to Render:

| Key | Value |
|-----|--------|
| `CLERK_JWKS_URL` | full JWKS URL above |

---

## Step 4 — Enable Google in Clerk

1. **Configure** → **SSO connections** (or **User & authentication** → **Social**)
2. Enable **Google**
3. Clerk provides a Google setup wizard — follow it (you use **Clerk’s** Google app, not a separate Google Cloud OAuth client for login)

---

## Step 5 — Add allowed origins (Vercel + local)

1. **Configure** → **Domains** (or **Paths** / allowed origins)
2. Add:
   - `http://localhost:3000` (local frontend)
   - Your Vercel URL, e.g. `https://helm.vercel.app`
   - Your custom domain when you attach it

---

## Step 6 — Environment variables

### Render (API)

```env
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://....clerk.accounts.dev/.well-known/jwks.json
```

When Clerk is set, Helm **automatically uses Clerk** instead of `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` for login.

### Vercel (frontend)

```env
REACT_APP_CLERK_PUBLISHABLE_KEY=pk_test_...
```

Leave `REACT_APP_BACKEND_URL` empty if you use `vercel.json` to rewrite `/api` → Render.

Redeploy **both** after adding env vars.

---

## Step 7 — Test sign-in

1. Open your site → **/login**
2. You should see Clerk’s sign-in (styled dark/gold)
3. Sign in with Google
4. You should land in `/app` (create company if first time)
5. **Sign out** → sign in again → **same company** (needs Atlas working)

---

## How it works in Helm

1. User signs in with **Clerk** (frontend)
2. Frontend sends Clerk session JWT to `POST /api/auth/clerk`
3. Backend verifies JWT, upserts user by **`clerk_id`** + email in Mongo
4. Backend sets Helm’s **httpOnly session cookie** (same as before)
5. All workspaces, billing, AI, etc. work unchanged

---

## Note: Google Calendar integration is separate

Clerk Google = **login only**.

Helm’s **Integrations** page uses a **different** Google OAuth (Calendar/Gmail) stored on the workspace. You can set that up later in Google Cloud Console — it does not replace Clerk.

---

## Troubleshooting

| Problem | Fix |
|--------|-----|
| Blank login / Clerk error | Check `REACT_APP_CLERK_PUBLISHABLE_KEY` on Vercel; redeploy |
| 401 on `/api/auth/clerk` | Check `CLERK_SECRET_KEY` + `CLERK_JWKS_URL` on Render |
| Redirect loop | Ensure Vercel `/api` rewrite points to correct Render host |
| New account every login | Atlas `MONGO_URL` wrong or DB not persistent — see `docs/ATLAS_SETUP.md` |
