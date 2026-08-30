# Helm — start here (simple)

You only need **4 accounts** (same logins you already have):

| What | Account | URL |
|------|---------|-----|
| **Code** | GitHub **Tans2101** (your main) | github.com/Tans2101 |
| **Database** | MongoDB Atlas | cloud.mongodb.com |
| **Sign-in** | Clerk | clerk.com |
| **Hosting** | Render (API) + Vercel (website) | render.com + vercel.com |

---

## Step 0 — Put code on GitHub **Tans2101**

Right now the latest code lives on **`tansherd21/Helm---Company-Cockpit`**.

**Easiest (if you control both GitHub accounts):**

1. Log into GitHub as **tansherd21**
2. Open https://github.com/tansherd21/Helm---Company-Cockpit
3. **Settings** → scroll to **Danger Zone** → **Transfer ownership**
4. Transfer to **`Tans2101`**
5. Repo becomes `https://github.com/Tans2101/Helm---Company-Cockpit`

**Or create a fresh repo on Tans2101** (on your Mac, after creating empty repo `Tans2101/helm`):

```bash
git clone https://github.com/tansherd21/Helm---Company-Cockpit.git
cd Helm---Company-Cockpit
git remote add tans2101 https://github.com/Tans2101/helm.git
git push tans2101 main
```

---

## Step 1 — MongoDB Atlas

See **docs/ATLAS_SETUP.md**

You need two values for Render:

- `MONGO_URL` = `mongodb+srv://...` (from Atlas → Connect → **Drivers** → Python)
- `DB_NAME` = `helm`

---

## Step 2 — Clerk

See **docs/CLERK_SETUP.md**

| Where | Key | Value |
|-------|-----|--------|
| **Render** | `CLERK_SECRET_KEY` | `sk_test_...` |
| **Render** | `CLERK_JWKS_URL` | `https://....clerk.accounts.dev/.well-known/jwks.json` |
| **Vercel** | `REACT_APP_CLERK_PUBLISHABLE_KEY` | `pk_test_...` |

---

## Step 3 — Render (API)

1. render.com → same login as always → **New Web Service**
2. Connect **`Tans2101/Helm---Company-Cockpit`** (after Step 0)
3. Branch: **`main`**
4. Root directory: **`backend`**
5. Build: `pip install -r requirements.txt`
6. Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`
7. Paste env vars from **backend/.env.example**

---

## Step 4 — Vercel (website)

1. vercel.com → **New Project** → same GitHub repo
2. Root: **`frontend`**, branch **`main`**
3. Env: `REACT_APP_CLERK_PUBLISHABLE_KEY=pk_test_...`
4. Edit **`frontend/vercel.json`** — put your Render URL in the rewrite
5. Deploy

---

## Step 5 — Test

1. `https://YOUR-API.onrender.com/api/health` → `"mongo": true`
2. Open your Vercel URL → Login → Google → create company
3. Sign out → sign in again → **same company**

Done.
