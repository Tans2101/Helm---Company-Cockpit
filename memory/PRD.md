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
- Telemetry: KPIs w/ sparklines, MRR-vs-target, funnel, risk matrix (scatter).
- Financials: MRR/ARR/runway/burn/cash, revenue-vs-expenses, burn, expense pie, scenarios.
- Tasks: drag-and-drop Kanban (4 columns), persists via PATCH.
- Reports: sales/production/procurement cards + AI Weekly CEO Pack (Pro).
- Team Bandwidth: utilization bars, overload flags.
- Calendar: meeting intelligence with prep notes.
- People: roster with trust scores, quality, tenure.
- Ask Kalun: streaming Claude chat grounded in live company data; free = 5 msgs/day.
- Integrations: 6 providers, connect/disconnect (live toggles Pro-gated).
- Billing: Free vs Pro, Stripe checkout, /payment/success + /payment/cancel; demo reset-plan.
- Plan gating verified: free → 403 on briefing/generate, weekly-pack, integration toggle.
- Tested: backend 100% (41 pytest), frontend 100%. No open bugs.

## Backlog
- P1: Real integrations (Google Calendar, QuickBooks, GitHub sync, Slack push).
- P1: Multi-company / multi-user (currently single seeded company).
- P2: Ask Kalun multi-turn memory carry-over; email/Slack delivery of morning briefing.
- P2: Gantt view for Tasks; CORS origin allowlist hardening for production.
- P2: Expired-session cleanup job; richer outcome-check tracking on decisions.

## Next Tasks
- Wire a first real integration (Google Calendar) behind Pro.
- Add scheduled morning-briefing generation + notification.
