# Cloudflare R2 setup (document uploads)

Trenston stores bill/receipt uploads in a **private** Cloudflare R2 bucket (S3-compatible). Users never see R2 credentials — you configure them once on Render.

Until these vars are set, Financials → **Upload a bill** returns `503 Document storage is not configured`.

---

## 1. Create the bucket

1. Open [Cloudflare Dashboard](https://dash.cloudflare.com/) → **R2 Object Storage**.
2. **Create bucket** — name e.g. `helm-documents` (or `helm-documents-prod`).
3. Leave the bucket **private** (no public access / custom domain required).
4. Note your **Account ID** (R2 overview sidebar, or the account home URL).

---

## 2. Create an API token

1. R2 → **Manage R2 API Tokens** (or Account API Tokens scoped to R2).
2. Create a token with **Object Read & Write** on the bucket you created (or account-wide R2 edit if you prefer one token).
3. Copy **Access Key ID** and **Secret Access Key** once — Cloudflare only shows the secret at creation time.

---

## 3. Paste on Render

Render → **helm-company-cockpit** → **Environment** → add:

| Variable | Value |
|----------|--------|
| `R2_ACCOUNT_ID` | Cloudflare account id (32 hex chars) |
| `R2_ACCESS_KEY_ID` | From the R2 API token |
| `R2_SECRET_ACCESS_KEY` | From the R2 API token |
| `R2_BUCKET_NAME` | Exact bucket name, e.g. `helm-documents` |
| `R2_ENDPOINT` | Optional if `R2_ACCOUNT_ID` is set. Otherwise: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |

Trenston derives `R2_ENDPOINT` from `R2_ACCOUNT_ID` when the endpoint is blank.

**Redeploy** the Render service after saving (env changes need a new deploy).

---

## 4. Verify

With `SETUP_SECRET` from Render:

```bash
curl -sf "https://www.trenston.com/api/setup/status" \
  -H "X-Setup-Secret: YOUR_SETUP_SECRET"
```

Expect `"r2": { "configured": true, "ok": true, "bucket": "helm-documents" }`.

Or in the app: Financials → upload a small PDF/PNG/JPEG bill → extraction form opens.

Locally (with the same env loaded):

```bash
cd backend && python -c "import storage; print(storage.probe_r2())"
```

---

## Security notes

- Keep the bucket private. The API serves files via short-lived **presigned URLs** only.
- Do not put R2 keys in Vercel — they belong on Render only.
- Rotate the R2 token if it leaks; update Render and redeploy.
