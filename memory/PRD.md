# Helm — CEO Operating System (PRD)

## Product
CEO-only cockpit for seed/Series A companies (~8–40 people). Synthesizes finance, sales, people, and ops into a morning briefing and decision workflow. Tagline: **CEO Operating System**. Dark graphite + gold UI.

## Stack (production — 2026)
| Layer | Technology |
|-------|------------|
| Frontend | React 19 (CRA), Vercel, Clerk sign-in |
| API | FastAPI on Render, Python 3.12 |
| Database | MongoDB Atlas (`DB_NAME=helm`) |
| Auth | Clerk (primary) or first-party Google OAuth fallback |
| AI | Direct Anthropic API (`backend/llm.py`) |
| Billing | Paddle only (nonce checkout + webhook idempotency) |
| Email | Resend |

## Routing
- `/` — marketing (Landing)
- `/about`, `/features`, `/pricing`, `/integrations` — mission, product, pricing, integrations
- `/login` — Clerk or Google
- `/privacy`, `/terms` — legal placeholders `[COMPANY_*]`
- `/app/*` — authenticated cockpit (Briefing, Pipeline, Financials, etc.)

## Pricing
<!-- Source of truth: frontend/src/lib/marketingCopy.js → PLANS (keep backend/plans.py aligned). Do not invent dollar figures here. -->
- Four tiers via Paddle: **Free** $0 (3 seats), **Starter** $15/mo (10 seats), **Growth** $39/mo (25 seats), **Business** $99/mo (50 seats).
- Public crawlable page: `/pricing` (also summarized on Landing). Paid plans include a 7-day trial.
- Sign up → enter `/app`; Free works without checkout; paid plans upgrade via Billing / Paddle.

## Tagline
**Run the business. Don't chase it.**

## Access packs
`owner`, `exec`, `finance`, `hr`, `sales`, `ops`, `member` — permissions via `PACK_PERMS`; sales pack home → `/app/sales` (Pipeline).

## Security / production defaults
- CORS allowlist (`CORS_ORIGINS`); optional `CORS_ORIGIN_REGEX` for preview hosts — never `.*`
- `OAUTH_STATE_SECRET` dedicated in production; OAuth redirect allowlist
- `ALLOW_DEMO_LOGIN=false`, `DEMO_RESET_ENABLED=false`
- Session httpOnly cookies; no `session_token` in JSON bodies
- GDPR: `GET /api/account/export`, `DELETE /api/account`, `DELETE /api/workspaces/current`

## Billing
- Paddle: `POST /api/billing/paddle/config`, webhook `/api/webhook/paddle`
- Portal: `POST /api/payments/paddle/portal`
- Webhooks handle `transaction.completed`, `subscription.canceled`, `subscription.past_due`
- Display prices from plan catalog (`marketingCopy.js` / `plans.py`), not a single `PRO_PRICE`

## Ops
- `GET /api/health` — Mongo ping
- Indexes: users, memberships, workspaces (`join_code`), sessions (`session_token` + TTL on `expires_at`), paddle_events
- Deploy: see `docs/DEPLOY.md`, `docs/RENDER_SETUP.md`, `docs/CLERK_SETUP.md`, `docs/ATLAS_SETUP.md`

## Out of scope (current)
- Stripe (removed)
- Emergent auth/LLM in production path
- Lawyer-reviewed legal counsel; SOC2
