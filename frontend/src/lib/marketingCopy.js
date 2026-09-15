/** Shared marketing copy — keep Landing, About, Features, and auth pages aligned. */

export const TAGLINE = "Run the business. Don't chase it.";
export const CATEGORY = "CEO Operating System";
export const AUDIENCE = "Built for CEOs running companies of up to 50 people.";
export const FOUNDER_NAME = "Tansher Dhawan";
export const FOUNDER_ROLE = "CEO & Founder";
export const FOUNDER_CREDIT = `${FOUNDER_NAME}, ${FOUNDER_ROLE}`;
export const PUBLIC_CONTACT_EMAIL = "contact@helmcontrol.online";
export const PUBLIC_CONTACT_MAILTO = `mailto:${PUBLIC_CONTACT_EMAIL}`;
export const FOUNDER_NOTE =
  "Helm is built and run by Tansher Dhawan, CEO & Founder — a CEO making the cockpit he wished existed for running a company of this size."

export const HERO_SUB =
  "Helm gives owners one clear view of money, people, work, and decisions. Open it whenever you need signal — see what changed, make the call, and get back to running the business.";

export const MISSION =
  "Helm makes leadership less chaotic. We give CEOs quiet control by turning scattered company data into clear decisions — so you run the business instead of chasing it.";

export const VISION =
  "A world where running a company doesn't mean drowning in dashboards — leaders see what matters, decide fast, and delegate with confidence.";

export const ABOUT_STORY =
  "Helm started from a simple frustration: CEOs running companies of up to 50 people waste hours opening twelve tabs — Slack, the CRM, the finance sheet, the shop floor, email — and still lack a clear picture of what actually needs them. The data exists. The synthesis doesn't. We built Helm to be the cockpit that pulls signal in, ranks what matters, and turns it into decisions and handoffs — not another dashboard to maintain.";

export const VALUES = [
  {
    title: "Signal over noise",
    body: "Every screen in Helm answers one question: what does the CEO need to know or do right now? If it doesn't help you decide or delegate, it doesn't belong.",
  },
  {
    title: "Quiet control",
    body: "No engagement loops, no notification spam. Helm respects that your attention is the company's scarcest resource.",
  },
  {
    title: "Honest synthesis",
    body: "AI recommendations cite your real numbers — cash, pipeline, team load — not generic advice. When data is missing, Helm says so.",
  },
];

export const WHO_HELM_IS_FOR = [
  {
    title: "CEOs of companies up to 50",
    body: "You're still in the weeds but shouldn't be drowning in them. Helm gives you a clear view to share with your leadership team — without hiring a chief of staff.",
  },
  {
    title: "Owner-operators & traditional businesses",
    body: "Manufacturing, services, agencies, family companies. Helm is a cockpit for running the operation, not a tool only venture-backed startups use.",
  },
  {
    title: "Leadership teams",
    body: "From a handful of people to fifty — finance, sales, ops, and production keep their lanes. You get one synthesized view.",
  },
];

export const CEO_DAY = [
  { title: "Briefing", body: "Three columns: what changed, what to decide, what to delegate — plus AI synthesis from your live data, and important Gmail threads with AI draft replies you review before sending." },
  { title: "Decision Center", body: "Pending approvals ranked by impact. Helm recommends which to tackle first and why." },
  { title: "Ask Helm", body: "\"What's our biggest risk this quarter?\" — answered from your financials and pipeline, not the internet." },
  { title: "CEO Pack", body: "A summary of growth, cash, team pulse, and open decisions — generated in one click, ready to share with your leadership team." },
];

export const PRICING_FAQ = [
  { q: "Is there a free plan?", a: "Yes. Free includes 3 seats, 5 free AI extracts to try it (then upgrade), Ask Helm (10 messages/month), and the AI briefing. Paid plans add monthly extract quotas, more seats, and QuickBooks." },
  { q: "Is there a free trial?", a: "Yes. Starter, Growth, and Business include a 7-day free trial. Cancel before it ends and you won't be charged." },
  { q: "Can my leadership team use Helm?", a: "Yes. Free supports up to 3 members, Starter up to 10, Growth up to 25, and Business up to 50 — with role-based access packs." },
  { q: "What integrations are included?", a: "Paid plans can connect Google Calendar and QuickBooks. Free stays manual-only." },
  { q: "Can I cancel anytime?", a: "Yes. Manage billing through Paddle. Cancellation takes effect at the end of the current billing period. No refunds after payment — use the trial to evaluate." },
];

export const FEATURE_CATEGORIES = [
  {
    id: "intelligence",
    label: "Executive intelligence",
    intro: "AI grounded in your company — not generic chatbot answers.",
    modules: ["Briefing", "Decision Center", "Ask Helm", "CEO Pack", "Gmail thread surfacing + AI draft replies"],
  },
  {
    id: "finance",
    label: "Finance & growth",
    intro: "Pipeline and financials are connected — won deals land as revenue, not a spreadsheet chase.",
    modules: ["Won deals become revenue", "Deal ownership & follow-ups", "Telemetry"],
  },
  {
    id: "operations",
    label: "Production, procurement & maintenance",
    intro: "Not three separate trackers. When production is blocked, Helm shows you exactly why — and jumps that item to the top of whichever queue is holding it up.",
    modules: [
      "Work order tracking",
      "Vendor memory",
      "Equipment reliability alerts",
      "Cross-department blocking",
    ],
  },
  {
    id: "people",
    label: "People & operations",
    intro: "Team access, department lanes, and integrations — everyone contributes, you stay in control.",
    modules: ["Integrations", "Team & Access"],
  },
];

/** Canonical pricing — keep in sync with backend/plans.py */
export const PLANS = [
  {
    id: "free",
    label: "Free",
    price: 0,
    for: "Small teams trying Helm",
    seats: 3,
    trialDays: 0,
    highlighted: false,
    includes: [
      "Up to 3 team members",
      "5 free AI extracts to try it, then upgrade",
      "Ask Helm (10 messages/month)",
      "AI briefing",
      "Dashboard & decisions",
      "No QuickBooks sync",
    ],
  },
  {
    id: "starter",
    label: "Starter",
    price: 15,
    for: "Small businesses",
    seats: 10,
    trialDays: 7,
    highlighted: true,
    includes: [
      "Up to 10 team members",
      "AI document upload (30/billing period)",
      "QuickBooks sync",
      "Ask Helm AI",
      "Calendar",
      "7-day free trial",
    ],
  },
  {
    id: "growth",
    label: "Growth",
    price: 39,
    for: "Growing businesses",
    seats: 25,
    trialDays: 7,
    highlighted: false,
    includes: [
      "Up to 25 team members",
      "AI document upload (150/billing period)",
      "Priority QuickBooks sync",
      "Advanced reports & CEO Pack",
      "7-day free trial",
    ],
  },
  {
    id: "business",
    label: "Business",
    price: 99,
    for: "Larger companies",
    seats: 50,
    trialDays: 7,
    highlighted: false,
    includes: [
      "Up to 50 team members",
      "AI document upload (500/billing period)",
      "Priority support",
      "Everything in Growth",
      "7-day free trial",
    ],
  },
];

/** @deprecated — use PLANS; kept for older imports */
export const PRO_PRICE = 15;
export const HELM_PRICE = PRO_PRICE;

export const PRO_FEATURES = PLANS.find((p) => p.id === "starter").includes;
export const HELM_FEATURES = PRO_FEATURES;

export const PRODUCT_FACTS = [
  { v: "3 seats", l: "included on the free plan" },
  { v: "7", l: "department workflows included" },
  { v: "1", l: "weekly leadership update" },
  { v: "PDF + Excel", l: "financial exports for your accountant" },
];

export const PROBLEMS = [
  {
    title: "The answer is scattered",
    body: "What needs your attention lives across Slack, the CRM, the finance sheet, the floor, and six dashboards. Nobody has the whole picture — least of all you.",
  },
  {
    title: "You react instead of lead",
    body: "By the time a problem reaches you, it's already a fire. Cash, delivery, and overload creep up silently between check-ins.",
  },
  {
    title: "Dashboards ≠ decisions",
    body: "More charts don't help. You need synthesis — the one number that moved, the one call to make, the one thing to hand off.",
  },
];

export const HOW_IT_WORKS = [
  { n: "01", title: "Your team updates the work", body: "Finance, sales, operations, and other departments use their own simple queues. Connect QuickBooks and Google where useful." },
  { n: "02", title: "Helm prepares your briefing", body: "Money, work, blockers, and open decisions are put in one short briefing. Missing information is called out plainly." },
  { n: "03", title: "You decide and hand off", body: "Approve, follow up, or assign the next step. Helm keeps the owner and outcome visible so decisions do not disappear." },
];

export const FEATURE_HIGHLIGHTS = [
  { title: "Briefing", body: "What changed, what to decide, what to delegate — synthesized from your live company data." },
  { title: "Decision Center", body: "Approvals with AI recommendations and confidence scores, plus outcome checks." },
  { title: "Runway & Burn", body: "Revenue, expenses, and cash tracking — always know where the money stands." },
  { title: "Ask Helm", body: "Your executive AI chief-of-staff, grounded in your live company data." },
];

/** Department lanes — enable only what the company actually uses. */
export const DEPARTMENTS_SECTION = {
  label: "Departments",
  title: "Turn on only the departments your company actually needs.",
  intro:
    "Give each team its own lane — Procurement, Production, Accounting & Finance, Sales, Legal, HR, Engineering & Maintenance — while you see everything from the top. Disable what you don't use.",
  items: [
    {
      name: "Procurement",
      icon: "package",
      body: "A purchase request queue: requested, approved, ordered, delivered — each request moves on its own.",
    },
    {
      name: "Production",
      icon: "factory",
      body: "An ordered production chain. Custom stages with status and owners; leads reorder the line as work flows.",
    },
    {
      name: "Accounting & Finance",
      icon: "landmark",
      body: "Your finance team logs revenue and expenses. Helm turns that into live cash, revenue, and spend across the cockpit.",
    },
    {
      name: "Sales",
      icon: "briefcase",
      body: "Deal pipeline by stage — open value and wins roll straight into the briefing.",
    },
    {
      name: "Legal",
      icon: "scale",
      body: "A matter queue for contracts and reviews, from draft through signed and filed, with documents attached.",
    },
    {
      name: "HR",
      icon: "users",
      body: "Per-hire onboarding from a reusable template — each new hire gets their own checklist with assignees.",
    },
    {
      name: "Engineering & Maintenance",
      icon: "wrench",
      body: "A ticket queue for equipment: reported, diagnosed, in repair, resolved — assign a technician and track it.",
    },
  ],
};

export const FEATURE_MODULES = [
  {
    title: "Briefing",
    ceoValue: "Know what changed and what needs you — whenever you open Helm.",
    body: "Three columns — what changed, what to decide, what to delegate — plus AI synthesis when you need the full picture.",
    example: "Revenue is ahead of plan, but engineering capacity risk is rising. Approve the infra reservation.",
  },
  {
    title: "Decision Center",
    ceoValue: "Every open decision, ranked by impact.",
    body: "Approve, follow up, or delegate with AI confidence scores. Helm tracks whether outcomes actually landed.",
    example: "Six pending approvals. Helm recommends the $40K reservation first — 4.2-month payback.",
  },
  {
    title: "Won deals become revenue",
    ceoValue: "Close the deal once — financials and production follow.",
    body: "Moving a deal to won logs the revenue automatically and offers a production work order from the same deal — pipeline and financials stay linked.",
    example: "Acme Enterprise closes at $25k. Revenue appears in Financials; Helm asks if you want a work order started.",
  },
  {
    title: "Deal ownership & follow-ups",
    ceoValue: "Real owners, planned next steps — not free-text ghosts.",
    body: "Deals link to Sales teammates, with next-step and follow-up dates so quiet deals surface before they stall.",
    example: "Riley owns the negotiation. Call-back Thursday is on the card — Helm reminds before it slips.",
  },
  {
    title: "Telemetry",
    ceoValue: "Live KPIs — signal over noise.",
    body: "Headcount, open tasks, MRR, and burn in one view. No digging through five dashboards.",
    example: "MRR up 8% MoM. Open tasks down. One team member overloaded.",
  },
  {
    title: "Ask Helm",
    ceoValue: "Your executive chief-of-staff, on call.",
    body: "Ask anything about your company — grounded in live workspace data, not generic AI.",
    example: "What's our biggest risk this quarter? Helm answers from your actual financials and pipeline.",
  },
  {
    title: "CEO Pack",
    ceoValue: "Leadership synthesis in one click.",
    body: "A plain-English update covering what happened, what needs attention, and what to do next — ready for your leadership team.",
    example: "Financial snapshot, team updates, and open decisions — formatted to forward, not rebuilt in slides.",
  },
  {
    title: "Gmail thread surfacing + AI draft replies",
    ceoValue: "Inbox signal without living in email.",
    body: "Surfaces important Gmail threads in the cockpit and drafts replies you can send — grounded in company context, not a blank compose box.",
    example: "A customer thread needs a decision. Helm drafts the reply; you edit and send.",
  },
  {
    title: "Work order tracking",
    ceoValue: "Production status without a separate system.",
    body: "Work orders move through a fixed flow — Awaiting Materials, In Production, Quality Check, Completed — with overdue detection and average cycle time.",
    example: "Three orders awaiting materials. One past due. Average cycle time visible without a spreadsheet.",
  },
  {
    title: "Vendor memory",
    ceoValue: "Re-order without starting from scratch.",
    body: "Procurement remembers past vendors and prices per item, tracks expected delivery, and flags overdue requests by priority.",
    example: "Same bracket as last quarter — Helm recalls the vendor and last price when you raise the request.",
  },
  {
    title: "Equipment reliability alerts",
    ceoValue: "Notice the machine that keeps coming back.",
    body: "Maintenance tickets for equipment issues, plus reliability alerts when the same machine repeats — and ticket-open downtime totals.",
    example: "Press #3 logged three tickets in 90 days. Helm flags it before the next breakdown.",
  },
  {
    title: "Cross-department blocking",
    ceoValue: "See why production is stuck — in one place.",
    body: "A blocked work order shows the part still in transit or the machine still in repair, and that item jumps to the top of its queue automatically.",
    example: "WO-441 blocked on a bearing order and a mill repair — both sit at the top of Procurement and Maintenance.",
  },
  {
    title: "Integrations",
    ceoValue: "Your team keeps their tools. You get the picture.",
    body: "Connect Google Calendar and QuickBooks where they fit. Manual entry stays available when a system is not connected.",
    example: "Finance logs in QuickBooks. Sales lives in the pipeline. You see it all in the briefing.",
  },
  {
    title: "Team & Access",
    ceoValue: "Invite your team with the right lane.",
    body: "Role-based packs plus per-department access. Turn on only the departments you need — each team works in its own lane; you see everything from the top.",
    example: "Your plant lead owns Production. Purchasing runs the request queue. You still see the synthesis in the briefing.",
  },
];

/** Public Help page — how Helm works, without a mandated schedule. */
export const HOW_TO_USE_INTRO = {
  title: "How to use Helm",
  subtitle: "Your CEO operating system — open it, get the signal, decide, delegate, and get back to running the company.",
  lead: "Helm isn't another dashboard to maintain. Open it whenever you need signal, make the call, delegate the rest — then get back to building.",
};

export const HOW_TO_USE_MODULES = [
  { nav: "Briefing", path: "/app", tip: "What changed, what needs a decision, and what to hand off — synthesized for leadership." },
  { nav: "My Day", path: "/app/me", tip: "Your calendar and top tasks in one view so you stay oriented on your own work." },
  { nav: "Decisions", path: "/app/decisions", tip: "Where approvals live. Act or delegate; Helm follows up until outcomes land." },
  { nav: "Ask Helm", path: "/app/ask", tip: "Executive Q&A from your live data — e.g. \"What's stuck in procurement?\" or \"What's open in the pipeline?\"" },
  { nav: "Telemetry", path: "/app/telemetry", tip: "Headcount, open tasks, revenue, and cash on one screen when you need a number." },
  { nav: "Financials", path: "/app/financials", tip: "Revenue, expenses, and cash position for leadership updates." },
  { nav: "Pipeline", path: "/app/sales", tip: "Deal stages and open pipeline at a glance." },
  { nav: "Reports", path: "/app/reports", tip: "CEO Pack — one click for financials, team pulse, and open decisions to share with leadership." },
  { nav: "Departments", path: "/app/settings", tip: "Turn on Procurement, Production, Legal, HR, and more — each team its own lane." },
  { nav: "Team & Access", path: "/app/members", tip: "Invite CFO, VP Sales, and ops to contribute while you keep the synthesized view." },
  { nav: "Integrations", path: "/app/integrations", tip: "Connect Google Calendar, QuickBooks, and other tools once — signal flows in automatically." },
];

export const HOW_TO_USE_CHECKLIST = [
  "Open your Briefing",
  "Clear or delegate one Decision",
  "Connect at least one integration",
  "Invite a leadership team member",
  "Generate your first CEO Pack",
];
