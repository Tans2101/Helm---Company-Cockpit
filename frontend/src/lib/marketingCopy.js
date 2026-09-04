/** Shared marketing copy — keep Landing, About, Features, and auth pages aligned. */

export const TAGLINE = "Run the business. Don't chase it.";
export const CATEGORY = "CEO Operating System";
export const AUDIENCE = "Built for seed & Series A CEOs running teams of 8–40.";

export const HERO_SUB =
  "Helm is the command center for CEOs. It pulls your company's real status in, synthesizes the signal, and tells you the one thing to decide — and who to hand the rest to.";

export const MISSION =
  "Helm makes leadership less chaotic. We give CEOs quiet control by turning scattered company data into clear daily decisions — so you run the business instead of chasing it.";

export const VISION =
  "A world where running a company doesn't mean drowning in dashboards — leaders see what matters, decide fast, and delegate with confidence.";

export const ABOUT_STORY =
  "Helm started from a simple frustration: CEOs at seed and Series A stage spend their mornings opening twelve tabs — Slack, the CRM, the finance sheet, Jira, email — and still walk into standup without a clear picture of what actually needs them. The data exists. The synthesis doesn't. We built Helm to be the one place a CEO opens first: a cockpit that pulls signal in, ranks what matters, and turns it into decisions and handoffs — not another dashboard to maintain.";

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
    body: "AI recommendations cite your real numbers — runway, pipeline, team load — not generic advice. When data is missing, Helm says so.",
  },
];

export const WHO_HELM_IS_FOR = [
  {
    title: "Seed & Series A CEOs",
    body: "You're still in the weeds but shouldn't be drowning in them. Helm gives you board-ready visibility without hiring a chief of staff.",
  },
  {
    title: "Founder-operators",
    body: "You wear every hat. Helm separates what only you can decide from what your team should run — and tracks whether it landed.",
  },
  {
    title: "Leadership teams of 8–40",
    body: "Finance, sales, ops, and engineering each keep their tools. You get one synthesized view every morning.",
  },
];

export const CEO_DAY = [
  { time: "7:30 AM", title: "Morning Briefing", body: "Three columns: what changed, what to decide, what to delegate — plus AI synthesis from your live data." },
  { time: "9:00 AM", title: "Decision Center", body: "Six pending approvals ranked by impact. Helm recommends which to tackle first and why." },
  { time: "12:00 PM", title: "Ask Helm", body: "\"What's our biggest risk this quarter?\" — answered from your financials and pipeline, not the internet." },
  { time: "Friday", title: "Weekly CEO Pack", body: "Board-ready summary of growth, burn, team pulse, and open decisions — generated in one click." },
];

export const PRICING_FAQ = [
  { q: "Is there a free plan?", a: "Yes. Free is for solo founders — manual entries and the dashboard/briefing. Paid plans add AI upload, team seats, Ask Helm, and integrations." },
  { q: "Is there a free trial?", a: "Yes. Starter, Growth, and Business include a 7-day free trial. Cancel before it ends and you won't be charged." },
  { q: "Can my leadership team use Helm?", a: "Yes on paid plans. Starter supports up to 3 members, Growth up to 10, Business up to 25 — with role-based access packs." },
  { q: "What integrations are included?", a: "Paid plans can connect Google Calendar and QuickBooks. Free stays manual-only." },
  { q: "Can I cancel anytime?", a: "Yes. Manage billing through Paddle. Cancellation takes effect at the end of the current billing period. No refunds after payment — use the trial to evaluate." },
];

export const FEATURE_CATEGORIES = [
  {
    id: "intelligence",
    label: "Executive intelligence",
    intro: "AI grounded in your company — not generic chatbot answers.",
    modules: ["Morning Briefing", "Decision Center", "Ask Helm", "Weekly CEO Pack"],
  },
  {
    id: "finance",
    label: "Finance & growth",
    intro: "Runway, revenue, and pipeline — always current for your next board question.",
    modules: ["Pipeline & Financials", "Telemetry"],
  },
  {
    id: "people",
    label: "People & operations",
    intro: "Team access and integrations — everyone contributes, you stay in control.",
    modules: ["Integrations", "Team & Access"],
  },
];

/** Canonical pricing — keep in sync with backend/plans.py */
export const PLANS = [
  {
    id: "free",
    label: "Free",
    price: 0,
    for: "Solo founders trying it out",
    seats: 1,
    trialDays: 0,
    highlighted: false,
    includes: [
      "1 user",
      "Manual financial entries",
      "Dashboard & briefing",
      "No AI document upload",
      "No QuickBooks sync",
    ],
  },
  {
    id: "starter",
    label: "Starter",
    price: 15,
    for: "Small businesses",
    seats: 3,
    trialDays: 7,
    highlighted: true,
    includes: [
      "Up to 3 team members",
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
    seats: 10,
    trialDays: 7,
    highlighted: false,
    includes: [
      "Up to 10 team members",
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
    seats: 25,
    trialDays: 7,
    highlighted: false,
    includes: [
      "Up to 25 team members",
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
  { v: "3 min", l: "to your morning briefing" },
  { v: "12", l: "modules in one cockpit" },
  { v: "AI", l: "grounded in your company data" },
  { v: "1", l: "decision to focus on each day" },
];

export const PROBLEMS = [
  {
    title: "The answer is scattered",
    body: "What needs your attention lives across Slack, Jira, Salesforce, the finance sheet and six dashboards. Nobody has the whole picture — least of all you.",
  },
  {
    title: "You react instead of lead",
    body: "By the time a problem reaches you, it's already a fire. Runway, churn and overload creep up silently between board meetings.",
  },
  {
    title: "Dashboards ≠ decisions",
    body: "More charts don't help. You need synthesis — the one number that moved, the one call to make, the one thing to hand off.",
  },
];

export const HOW_IT_WORKS = [
  { n: "01", title: "Pulls it in", body: "Helm connects to Google, QuickBooks, Paddle and GitHub — your team keeps their tools, you get the signal." },
  { n: "02", title: "Synthesizes", body: "Every morning it distills finance, sales, people and risk into a three-line briefing. Signal over noise." },
  { n: "03", title: "You decide & delegate", body: "Approve, follow up, or hand off in a click — then Helm tracks whether the outcome actually landed." },
];

export const FEATURE_HIGHLIGHTS = [
  { title: "Morning Briefing", body: "What changed, what to decide, what to delegate — before your first meeting." },
  { title: "Decision Center", body: "Approvals with AI recommendations and confidence scores, plus outcome checks." },
  { title: "Runway & Burn", body: "Revenue, burn and scenario planning — always know how long you have to win." },
  { title: "Ask Helm", body: "Your executive AI chief-of-staff, grounded in your live company data." },
];

export const FEATURE_MODULES = [
  {
    title: "Morning Briefing",
    ceoValue: "Start every day knowing what changed and what needs you.",
    body: "Three columns — what changed, what to decide, what to delegate — plus AI synthesis when you need the full picture.",
    example: "Revenue is ahead of plan, but engineering capacity risk is rising. Approve the infra reservation today.",
  },
  {
    title: "Decision Center",
    ceoValue: "Every open decision, ranked by impact.",
    body: "Approve, follow up, or delegate with AI confidence scores. Helm tracks whether outcomes actually landed.",
    example: "Six pending approvals. Helm recommends the $40K reservation first — 4.2-month payback.",
  },
  {
    title: "Pipeline & Financials",
    ceoValue: "Runway and revenue at a glance for your next board question.",
    body: "MRR, burn, runway, and deal stages — live, not buried in a spreadsheet you update monthly.",
    example: "17 months runway at current burn. Two deals in negotiation worth $180K ARR.",
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
    title: "Weekly CEO Pack",
    ceoValue: "Board-ready synthesis in one click.",
    body: "AI-generated weekly summary of financials, team pulse, and execution — ready to share.",
    example: "Financial snapshot, team updates, and open decisions — formatted for your board prep.",
  },
  {
    title: "Integrations",
    ceoValue: "Your team keeps their tools. You get the picture.",
    body: "Google Calendar, Gmail, QuickBooks, GitHub, and more — signal flows into Helm automatically.",
    example: "Finance logs in QuickBooks. Sales lives in the pipeline. You see it all in the briefing.",
  },
  {
    title: "Team & Access",
    ceoValue: "Invite your leadership team with the right visibility.",
    body: "Role-based packs for finance, sales, ops, and HR — everyone contributes, you stay in control.",
    example: "Your CFO updates financials. Your VP Sales owns pipeline. You see the synthesis.",
  },
];

/** In-app onboarding — how CEOs use Helm day to day. */
export const HOW_TO_USE_INTRO = {
  title: "How to use Helm",
  subtitle: "Your CEO operating system in three rhythms: morning, during the day, and each week.",
  lead: "Helm isn't another dashboard to maintain. Open it once, get the signal, make the call, delegate the rest — then get back to building.",
};

export const HOW_TO_USE_RHYTHMS = [
  {
    id: "morning",
    label: "Every morning",
    time: "~5 minutes",
    icon: "sun",
    steps: [
      { title: "Open Briefing", body: "Start on the Briefing tab. Three columns tell you what changed overnight, what needs your decision, and what to hand off." },
      { title: "Scan Decisions", body: "Head to Decision Center. Approvals are ranked by impact — Helm recommends which to tackle first and why." },
      { title: "Check My Day", body: "My Day pulls your calendar and top tasks into one view so you walk into standup already oriented." },
    ],
  },
  {
    id: "day",
    label: "During the day",
    time: "As needed",
    icon: "zap",
    steps: [
      { title: "Ask Helm", body: "Need a fast read? Ask \"What's our runway at current burn?\" or \"What's stuck in the pipeline?\" — answers come from your live data." },
      { title: "Delegate from Decisions", body: "Approve, follow up, or assign. Helm tracks whether outcomes actually landed — no more decisions that vanish." },
      { title: "Glance Telemetry", body: "MRR, burn, headcount, open tasks — one screen when a board member Slacks you a number question." },
    ],
  },
  {
    id: "week",
    label: "Each week",
    time: "Friday · ~10 minutes",
    icon: "calendar",
    steps: [
      { title: "Generate CEO Pack", body: "Reports → Weekly CEO Pack. One click produces a board-ready summary of financials, team pulse, and open decisions." },
      { title: "Connect integrations", body: "Integrations pulls signal from Google Calendar, Gmail, QuickBooks, and GitHub — your team keeps their tools." },
      { title: "Invite your leadership team", body: "Team & Access lets CFO, VP Sales, and ops contribute data while you keep the synthesized view." },
    ],
  },
];

export const HOW_TO_USE_MODULES = [
  { nav: "Briefing", path: "/app", tip: "Your daily starting point — always open this first." },
  { nav: "Decisions", path: "/app/decisions", tip: "Where approvals live. Act or delegate; Helm follows up." },
  { nav: "Ask Helm", path: "/app/ask", tip: "Executive Q&A grounded in your company, not the internet." },
  { nav: "Financials", path: "/app/financials", tip: "Runway, burn, and scenarios for board prep." },
  { nav: "Pipeline", path: "/app/sales", tip: "Deal stages and weighted pipeline at a glance." },
  { nav: "Integrations", path: "/app/integrations", tip: "Connect tools once; signal flows in automatically." },
];

export const HOW_TO_USE_CHECKLIST = [
  "Skim your Morning Briefing",
  "Clear or delegate one Decision",
  "Connect at least one integration",
  "Invite a leadership team member",
  "Generate your first Weekly CEO Pack",
];
