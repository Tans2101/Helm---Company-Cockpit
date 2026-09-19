/**
 * Public changelog — plain-language entries for real shipped work only.
 * Add a row when something customer-visible lands; do not list aspirational features.
 * Dates are approximate ship days from git history on main.
 */
export const CHANGELOG_ENTRIES = [
  {
    date: "2026-09-19",
    title: "Faster tab switching across the cockpit",
    body: "Department pages keep recently loaded data when you switch tabs, so revisiting Briefing, Financials, HR, or Production no longer resets to a loading skeleton every time.",
  },
  {
    date: "2026-09-19",
    title: "Google Calendar and Gmail are personal connections",
    body: "Each teammate connects their own Google account. Meetings and Gmail threads stay on that person’s connection — not a shared workspace mailbox.",
  },
  {
    date: "2026-09-19",
    title: "Public pricing page for crawlers and buyers",
    body: "Standalone /pricing with the live Free, Starter, Growth, and Business tiers, plus structured data and llms.txt so published prices match the product.",
  },
  {
    date: "2026-09-19",
    title: "Public integrations page",
    body: "A marketing page that lists what each connection actually does today — Google, QuickBooks, Xero, SAP Business One, HubSpot, and Slack webhook alerts.",
  },
  {
    date: "2026-09-18",
    title: "SAP Business One in Financials",
    body: "Pull A/R and A/P invoices from SAP Business One Service Layer into the same Financials and Decision Engine pipeline as QuickBooks and Xero.",
  },
  {
    date: "2026-09-18",
    title: "Honest financial zeros vs missing data",
    body: "Burn, MRR, and runway distinguish “not entered” from a confirmed zero, and future-dated ledger rows no longer inflate current metrics.",
  },
  {
    date: "2026-09-18",
    title: "Decision Center ranking and resilience",
    body: "Pending decisions rank by impact within severity, and a single failed AI draft no longer clears the rest of the decision board.",
  },
  {
    date: "2026-09-18",
    title: "Ask Helm stays inside your access lanes",
    body: "Ask Helm and department context respect membership and finance:write — no cross-lane leakage of Sales, HR, or financial figures you cannot open in the UI.",
  },
  {
    date: "2026-09-18",
    title: "AI summary freshness labels",
    body: "AI summaries surface when underlying department data may be stale, so leadership can tell synthesis from a live pull.",
  },
  {
    date: "2026-09-17",
    title: "Secure document library",
    body: "Private Cloudflare R2 storage with signed downloads for bills, receipts, and legal files — plus tighter controls on legal document access.",
  },
  {
    date: "2026-09-17",
    title: "Daily alerts and weekly digest email",
    body: "Render cron jobs schedule high-severity alerts and the weekly leadership pack email, separate from in-app Briefing.",
  },
  {
    date: "2026-09-17",
    title: "HR leave cancellation",
    body: "Employees can cancel their own pending leave requests without waiting on an HR lead.",
  },
  {
    date: "2026-09-17",
    title: "Billing clarity after Paddle checkout",
    body: "Plan state refreshes after checkout, seat and AI-extract over-limit usage is shown clearly, and Stripe leftover UI is gone.",
  },
  {
    date: "2026-09-16",
    title: "⌘K search across settings and site pages",
    body: "Quick search reaches settings sections and public marketing pages from inside the signed-in app.",
  },
];

export const CHANGELOG_INTRO =
  "What actually shipped in Helm — not a roadmap. Entries are written from product changes on main, in plain language.";
