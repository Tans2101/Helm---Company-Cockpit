# Kalun — CEO Operating System (PRD)

## Original Problem Statement
A CEO-only cockpit for seed/Series A companies (~8–40 people). Answers "What does the CEO need to know right now?" Employees stay in their tools (Jira, Slack, Salesforce); Kalun pulls status/KPIs in and pushes work out. Wedge: a morning executive briefing from real company data. Tagline: "CEO Operating System." Dark "quiet control" aesthetic — graphite (#09090b) + champagne gold (#c9a962), DM Sans + DM Mono, fixed 260px sidebar, high-density glass cards.

## User Choices (v1)
- Full UI shell with ALL modules + rich demo data
- AI powered by Claude Sonnet 4.6 (Emergent Universal LLM key)
- Emergent-managed Google login (auth)
- Real Stripe test-mode for Pro upgrade; other integrations mocked
- Pre-seeded fictional startup: Northwind Robotics (Series A, 24 people)

## Routing
- Public marketing homepage at `/` (Landing.jsx — hero with live briefing preview, problem, how-it-works, features, CTA).
- `/login` (Google sign-in). Cockpit is namespaced under `/app/*` (index = Briefing). OAuth redirect returns to `/app`.

## Architecture
- Frontend: React 19 + react-router 7, Tailwind, Recharts, framer-motion, sonner. Fixed sidebar shell, per-module pages, SSE chat.
- Backend: FastAPI + Motor (MongoDB). All routes under /api. Cookie/Bearer session auth.
- AI: emergentintegrations LlmChat → claude-sonnet-4-6 (briefing synthesis, Weekly CEO Pack, Ask Kalun streaming).
- Payments: emergentintegrations StripeCheckout (Flow B, shared test sandbox sk_test_emergent; Flow A blocked — default country PH unsupported). Pro = $149/mo.
- Data: single seeded company doc `kalun-demo` in Mongo (seed_data.py).

## User Persona
Solo founder/CEO of a small startup who wants synthesis over raw data — one command center.

## Implemented (2026-07-25)
- Emergent Google Auth: /auth/session, /auth/me, /auth/logout; ProtectedRoute + AuthCallback.
- Briefing (home): metrics, AI synthesis (Pro), what changed / decide / delegate.
- Decisions: approve/reject/delegate, AI recommendation + confidence, outcome checks.
- Telemetry, Financials, Tasks (drag Kanban), Reports (+AI Weekly CEO Pack), Team Bandwidth, Calendar, People, Ask Kalun (streaming Claude), Integrations, Billing (Stripe test-mode).
- Plan gating: free → 403 on briefing/generate, weekly-pack, integration toggle.

## Implemented (2026-07-26) — Multi-tenant + Integrations
- Multi-tenant workspaces: each user bootstraps their own seeded workspace; `workspaces` + `memberships` collections; all module endpoints scoped by principal.workspace_id (data isolation).
- Roles: owner vs member. `require(action)` dependency + perms_for; owner-only writes (decisions, invite, billing, integrations, briefing/pack). Member = read + tasks:move + ask:use.
- Team & Access page: invite by email (existing users auto-join; new emails join on first login), change role, remove member.
- Workspace switcher (sidebar) + create/switch workspace.
- Real OAuth integration framework: Google (Calendar+Gmail combined scopes) + QuickBooks — connect/callback/disconnect, tokens stored per workspace, HMAC-signed state (CSRF). Degrades gracefully when GOOGLE_/QUICKBOOKS_ env keys are empty (shows "Keys needed"). Google Calendar live-events fetch endpoint built.
- Data-only providers: Stripe (connected), GitHub/Slack/Salesforce (toggles).
- Tested: backend 100% (84 pytest, run with -n 0), frontend 100%. No open bugs.

## Implemented (2026-07-26) — Onboarding + Entry-driven Financials + Stripe import
- Empty-state onboarding: new workspaces start empty; CEO chooses "Explore with sample data" (loads Northwind + 36 financial entries) or "Start clean". POST /api/workspace/apply-template.
- Financials are now entry-driven and REAL: finance team logs revenue/expense entries in Helm (POST/PATCH/DELETE /api/financials/entries, PUT /api/financials/settings for cash & margin). Permission finance:write for owner + finance pack.
- compute_financials() aggregates entries → MRR/ARR/net-burn/runway/expense-breakdown/scenarios, which flow into Telemetry (MRR KPI + revenue trend) and the Briefing metrics — one source of truth across the cockpit.
- Stripe revenue import: POST /api/financials/import/stripe pulls succeeded charges → monthly recurring revenue entries (needs a real Stripe key; degrades to a clean 400 on the shared shim key, no data loss on empty result).
- Empty states across all modules (EmptyState in kit); Financials ledger UI with add/edit(delete)/import + cash/margin editor.
- Tested: backend 99/99 pytest (run -n 0), frontend 100%. Flow-through verified live (adding an entry moved MRR $248K→$256K). No open bugs.

## Implemented (2026-07-26) — Access packs (department operator roles)
- Access packs replace binary owner/member: `owner`, `exec`, `finance`, `hr`, `member`.
- `/auth/me` returns `role`, `perms[]`, `modules[]`, `home`. Restricted packs (finance/hr) only see their workbench modules; API + sidebar + route guards enforce the same map.
- Finance writes (`finance:write`) limited to owner + finance pack (general members are read-only on financials).
- Activity log: finance entry/settings/import writes append `activity_events` and prepend into Briefing `what_changed` so CEO sees live operator updates.
- Team & Access invite/change-role UI supports all packs; AuthCallback lands operators on their home (finance → Financials, hr → People).

## Known follow-ups (from code review, non-blocking)
- compute_financials MRR falls back to total revenue when no entry is marked recurring (label could mislead for one-off-only revenue).
- avg net burn ignores net-positive months (fine while burning).

## Pending credentials (to go live)
- GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (enable Calendar + Gmail APIs, add redirect URI /api/oauth/google/callback).
- QUICKBOOKS_CLIENT_ID / QUICKBOOKS_CLIENT_SECRET (Intuit app, redirect /api/oauth/quickbooks/callback).
- RESEND_API_KEY + SENDER_EMAIL (verified domain) to send real invitation emails. Until set, invites are created but emails no-op (logged).

## Implemented (2026-07-26) — Email invitations
- Resend integration: owner invites now send a branded (dark/gold) HTML "you've been added to Kalun" email via Resend. send_invite_email() runs non-blocking (asyncio.to_thread) and degrades gracefully to a no-op when RESEND_API_KEY is empty. invite response returns email_sent flag; Members UI toast reflects instant-join / email-sent / pending-invite.

## Backlog
- P1: Real integrations (Google Calendar, QuickBooks, GitHub sync, Slack push).
- P1: Multi-company / multi-user (currently single seeded company).
- P2: Ask Kalun multi-turn memory carry-over; email/Slack delivery of morning briefing.
- P2: Gantt view for Tasks; CORS origin allowlist hardening for production.
- P2: Expired-session cleanup job; richer outcome-check tracking on decisions.

## Next Tasks
- Wire a first real integration (Google Calendar) behind Pro.
- Add scheduled morning-briefing generation + notification.
