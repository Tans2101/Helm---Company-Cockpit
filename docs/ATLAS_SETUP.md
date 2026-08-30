# MongoDB Atlas — step-by-step for Helm

Helm stores **all company data** in MongoDB (users, workspaces, financials, deals, billing state, etc.). You need **MongoDB Atlas** — a hosted, persistent database.

On Render, set:
- `MONGO_URL` = connection string below
- `DB_NAME` = `helm`

---

## Step 1 — Create an Atlas account

1. Go to **https://cloud.mongodb.com**
2. Sign up or log in
3. Create an **Organization** (default name is fine)
4. Create a **Project** (e.g. `Helm`)

---

## Step 2 — Create a cluster

1. On the project home page, click **Create** or **Build a database**
2. Choose **Free** (sandbox) or **Flex** (low-cost paid) — either works to start
3. Pick a **cloud provider + region** (choose one close to your Render region, e.g. `us-east-1`)
4. Cluster name: `Cluster0` (default is fine)
5. Click **Create deployment** / **Create** and wait until status is **Active** (a few minutes)

---

## Step 3 — Create a database user

1. Atlas may prompt you during setup — if so, create a user there  
   **Or** go to **Database Access** (left sidebar under Security)
2. Click **Add New Database User**
3. Authentication: **Password**
4. Username: e.g. `helm_user`
5. Password: click **Autogenerate Secure Password** and **save it** in a password manager
6. Database User Privileges: **Read and write to any database**
7. Click **Add User**

---

## Step 4 — Allow network access (required for Render)

1. Go to **Network Access** (left sidebar under Security)
2. Click **Add IP Address**
3. Click **Allow Access from Anywhere**  
   - Adds `0.0.0.0/0`  
   - Render’s IPs are not fixed on starter plans, so this is required
4. Confirm

---

## Step 5 — Copy the connection string

1. Go to **Database** → **Clusters**
2. On your cluster, click **Connect**
3. Choose **Drivers**
4. Driver: **Python**, Version: **3.12 or later**
5. Copy the connection string. It looks like:

```text
mongodb+srv://helm_user:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

6. Replace `<password>` with your real database user password  
   - If the password contains `@ # / ?` etc., [URL-encode](https://www.mongodb.com/docs/atlas/troubleshoot-connection/#special-characters-in-connection-string-password) them

You do **not** need `/helm` in the URI — Helm uses `DB_NAME=helm` separately.

---

## Step 6 — Add to Render

1. Open your **Render** API service → **Environment**
2. Add:

| Key | Value |
|-----|--------|
| `MONGO_URL` | your full `mongodb+srv://...` string |
| `DB_NAME` | `helm` |

3. Save and **Redeploy**

---

## Step 7 — Verify

Open in a browser:

```text
https://YOUR-RENDER-API.onrender.com/api/health
```

You want:

```json
{"status":"ok","mongo":true}
```

If `mongo` is `false`, check: wrong password, IP not allowed, or typo in `MONGO_URL`.

---

## Why this matters for Helm

Emergent previews often used **ephemeral** databases — data disappeared between deploys, so every Google login felt like a **brand-new account**. Atlas is **durable**: same Google/Clerk user → same Helm user → same company workspace.
