# Integrations — Helm Control

Helm integrations are split into **OAuth connections** (per workspace) and **platform services** (configured once on Render). Set variables on your Render web service unless noted for Vercel.

Users never create API keys. Once you paste keys on Render, owners click **Connect** in the app.

## Paste these on Render (then redeploy)

| Service | Env vars | Where to get them |
|---------|----------|-------------------|
| **Google Calendar** | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → OAuth 2.0 Client (Web) |
| **QuickBooks** | `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET`, `QUICKBOOKS_ENV` (`production` or `sandbox`) | [Intuit Developer](https://developer.intuit.com/) → app → Keys |
| **Anthropic** | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | [Anthropic Console](https://console.anthropic.com/settings/keys) |
| **Cloudflare R2** | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT` | Cloudflare → R2 → Manage API tokens |
| **Resend** | `RESEND_API_KEY`, `SENDER_EMAIL` | [Resend](https://resend.com/) — optional until invites |
| **Paddle** | `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_PRICE_ID*`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_ENV` | Paddle dashboard — when charging |
| **Clerk** | already on Render | Sign-in |

## OAuth redirect URIs (register exactly)

Because Vercel proxies `/api` → Render, register the **www** URLs:

**Google Cloud → Credentials → your OAuth client → Authorized redirect URIs**

```
https://www.helmcontrol.online/api/oauth/google/callback
```

Also enable **Google Calendar API** for the project.

**Intuit Developer → your app → Keys → Redirect URI**

```
https://www.helmcontrol.online/api/oauth/quickbooks/callback
```

Scopes needed: Accounting (`com.intuit.quickbooks.accounting`).

Verify live config (no secrets exposed):

```
GET https://www.helmcontrol.online/api/setup/status
```

Look under `integrations` / `oauth_redirect_uris` — `configured: true` means the env vars are present.

## After keys are set

1. Redeploy the Render API (or wait for auto-deploy).
2. Sign in as a workspace **owner**.
3. Open **Integrations** → Connect Google Calendar / QuickBooks.
4. QuickBooks: after Connect, click **Sync to Financials**.
5. Financials uploads need R2 + Anthropic; Ask Helm / briefing need Anthropic.

## Coming soon

Gmail, GitHub, Slack, and Salesforce stay “Coming soon” in the UI until those OAuth apps are built.

## Quick tester flow

1. Sign in with Clerk.
2. Set `ANTHROPIC_API_KEY` (+ R2) → generate a briefing and upload a bill.
3. Connect Google Calendar → open Calendar.
4. Connect QuickBooks → Sync to Financials.
5. Invite a teammate (Resend sends email when `RESEND_API_KEY` is set).

See also `backend/.env.example` for the full variable list.
