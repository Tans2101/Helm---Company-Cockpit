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

export const PRO_PRICE = 8;

export const PRO_FEATURES = [
  "AI Morning Briefing & synthesis",
  "Full Decision Center with recommendations",
  "Weekly CEO Pack (AI-generated)",
  "Live integrations (Google, QuickBooks, GitHub)",
  "Unlimited Ask Helm",
  "Runway, pipeline, team bandwidth & reports",
];

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
