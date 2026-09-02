# Integrations — Helm Control

Helm integrations are split into **OAuth connections** (per workspace) and **platform services** (configured once on Render). Set variables on your Render web service unless noted for Vercel.

## Day 1 essentials

| Integration | What it does | Render env vars | Vercel env vars |
|-------------|--------------|-----------------|-----------------|
| **Google Calendar** | Pulls today's meetings into Calendar and the AI morning briefing | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | — |
| **QuickBooks** | Syncs purchases/invoices into Financials (burn, runway) | `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET`, `QUICKBOOKS_ENV` (`sandbox` or `production`) | — |
| **Helm AI (Anthropic)** | Briefing, Ask Helm, bill extraction | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (optional, default `claude-sonnet-5`) | — |
| **Document Storage (R2)** | Private PDF/image uploads on Financials | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT` | — |
| **Team Email (Resend)** | Invite emails when adding teammates | `RESEND_API_KEY`, `SENDER_EMAIL` | — |
| **Clerk Auth** | Sign-in (required for production) | `CLERK_SECRET_KEY`, `CLERK_JWKS_URL` | `VITE_CLERK_PUBLISHABLE_KEY` |

## Billing (when enabled)

| Integration | What it does | Render env vars |
|-------------|--------------|-------------------|
| **Paddle** | Pro checkout + customer portal | `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_PRICE_ID`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_ENV` |

Set `BILLING_ENFORCED=false` while building (default) so testers get full access without checkout.

## OAuth redirect URIs

Register these on Google Cloud Console and Intuit Developer:

- Google: `https://<your-render-host>/api/oauth/google/callback`
- QuickBooks: `https://<your-render-host>/api/oauth/quickbooks/callback`

Also set `APP_URL=https://www.helmcontrol.online` and `CORS_ORIGINS` to your Vercel frontend.

## Coming soon

Gmail, GitHub, Slack, and Salesforce require additional OAuth apps or scopes and are marked **Coming soon** in the Integrations UI.

## Quick tester flow

1. Sign in with Clerk.
2. Set `ANTHROPIC_API_KEY` on Render → generate a briefing and upload a bill on Financials.
3. Connect Google Calendar → open Calendar to see today's meetings.
4. Connect QuickBooks → **Sync to Financials** on Integrations.
5. Invite a teammate on Team → Resend sends the invite when `RESEND_API_KEY` is set.

See also `backend/.env.example` for the full variable list.
