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
- Financials are now entry-driven and REAL: finance team logs revenue/expense entries in Helm (POST/PATCH/DELETE /api/financials/entries, PUT /api/financials/settings for cash & margin). New permission finance:write granted to owner + member.
- compute_financials() aggregates entries → MRR/ARR/net-burn/runway/expense-breakdown/scenarios, which flow into Telemetry (MRR KPI + revenue trend) and the Briefing metrics — one source of truth across the cockpit.
- Stripe revenue import: POST /api/financials/import/stripe pulls succeeded charges → monthly recurring revenue entries (needs a real Stripe key; degrades to a clean 400 on the shared shim key, no data loss on empty result).
- Empty states across all modules (EmptyState in kit); Financials ledger UI with add/edit(delete)/import + cash/margin editor.
- Tested: backend 99/99 pytest (run -n 0), frontend 100%. Flow-through verified live (adding an entry moved MRR $248K→$256K). No open bugs.

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

## Implemented (2026-07-26) — Access Packs + Activity Log + People (Phases 0/1/3)
- Access packs replace binary owner/member: owner, exec, finance, hr, sales, ops, member. Each maps to a permission set + default home route. `pack_of()` keeps legacy owner/member rows backward-compatible. /auth/me returns pack, perms[], default_route, pack_label.
- Finance writes restricted to finance/owner/exec (member is read-only now).
- Activity Log: `activities` collection + `log_activity()`. Financial + People writes append an activity; GET /api/activities; CEO Briefing "what changed" prepends the last 5 activities.
- People CRUD (POST/PATCH/DELETE /api/people, people:write) with headcount sync to workspace.employees + avg_trust recompute.
- Members: invite/patch carry a pack (owner-only can grant owner); list returns pack + user_id + my_pack.
- Tested: 26 backend tests (test_packs_activity_people.py + updated suites), all green.

## Implemented (2026-07-26) — Employee workspace (My Day + Daily Updates + Tasks + Join UX)
- Product shift: Helm is ONE company workspace for EVERY employee, not a CEO-only cockpit.
- My Day (`/app/me`, default home for member/sales/ops): daily-update composer, "my tasks", team-updates strip. Owner/exec still land on Briefing.
- Daily Updates: `updates` collection, one-per-user-per-day (editable). POST /api/updates, GET /api/updates/me, GET /api/updates/today. Rolls up into Briefing what_changed[0] + a new `team_updates` array ("Today's team updates" section).
- Tasks personal + departmental: /api/tasks returns can_create/can_assign/my_user_id; POST /api/tasks (member → self; tasks:assign → assign to any workspace member); GET /api/tasks/me; move_task enforces ownership; move to done sets progress 100.
- Invite/join UX that can't fail: brand-new user with no membership → needs_workspace (WorkspaceGate: Create company OR Join with code). No more silent auto-CEO. Self-serve POST /api/workspaces works without a membership. Join by code: /api/workspaces/join-info, /join, /join-code (members:invite). build_workspace adds a 6-char join_code.
- Who-can-invite: owner = full incl. promote-to-owner; exec = members:invite + assign any pack EXCEPT owner (cannot change owners). members:manage (owner-only) required to remove members / touch owners.
- Frontend: src/lib/access.js (pack meta + hasPerm), MyDay.jsx, WorkspaceGate.jsx, Members/Tasks/Briefing/AppLayout/ProtectedRoute/AuthCallback updated.
- Tested: 26 backend tests (test_updates_myday_join_exec.py), all green.

## Implemented (2026-08-03) — Paddle Billing (live)
- Paddle Billing added ALONGSIDE Stripe (Stripe retained). LIVE keys in backend/.env (PADDLE_API_KEY, PADDLE_CLIENT_TOKEN, PADDLE_PRICE_ID, PADDLE_WEBHOOK_SECRET, PADDLE_ENV=production).
- Backend: POST /api/billing/paddle/config (billing:manage) mints a nonce bound to workspace+user (paddle_intents, 1h TTL); POST /api/webhook/paddle verifies Paddle-Signature HMAC (ts:body), idempotent via paddle_events unique _id, provisions plan=pro on transaction.completed / active subscription; nonce-binding prevents cross-workspace provisioning. billing/plans returns paddle_ready.
- Frontend: src/lib/paddle.js loads Paddle.js v2 + Initialize once; Billing.jsx primary CTA opens Paddle overlay checkout with customData {workspace_id, user_id, checkout_nonce}; "Secure checkout by Paddle".
- Tested: 7 Paddle tests (signature reject, provision, idempotency, nonce-binding, config auth-gating). NOTE: preview ingress/WAF returns 403 on programmatic POSTs to /api/webhook/paddle — webhook tests run against localhost:8001; deployed env is unaffected. Full suite 152 passed.

## Backlog (updated)
- P1: Sales pipeline + Ops risk WRITE loops (packs/nav exist; editors deferred).
- P1: Department-lead-scoped invites (finance invites finance, etc.).
- P1: Real integrations (Google Calendar, QuickBooks, GitHub sync, Slack push).
- P2: Scheduled morning-briefing email (Resend) + CEO approval notifications; Ask Helm multi-turn memory.
- P2: Manager pack (team-subset scoping); CORS allowlist hardening; expired-session cleanup.
