# Kalun — CEO Operating System (PRD)

## Original Problem Statement
A CEO-only cockpit for seed/Series A companies (~8–40 people). Answers "What does the CEO need to know right now?" Employees stay in their tools (Jira, Slack, Salesforce); Kalun pulls status/KPIs in and pushes work out. Wedge: a morning executive briefing from real company data. Tagline: "CEO Operating System." Dark "quiet control" aesthetic — graphite (#09090b) + champagne gold (#c9a962), DM Sans + DM Mono, fixed 260px sidebar, high-density glass cards.

## User Choices (v1)
- Full UI shell with ALL modules + rich demo data
- AI powered by Claude Sonnet 4.6 (Emergent Universal LLM key)
- Emergent-managed Google login (auth)
- Real Stripe test-mode for Pro upgrade; other integrations mocked
- Pre-seeded fictional startup: Northwind Robotics (Series A, 24 people)

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
