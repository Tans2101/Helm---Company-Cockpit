/** Shared marketing copy — keep Landing, About, Features, and auth pages aligned. */

export const TAGLINE = "Run the business. Don't chase it.";
export const CATEGORY = "CEO Operating System";
export const AUDIENCE = "Built for CEOs running companies of up to 50 people.";
export const FOUNDER_NAME = "Tansher Dhawan";
export const FOUNDER_ROLE = "CEO & Founder";
export const FOUNDER_CREDIT = `${FOUNDER_NAME}, ${FOUNDER_ROLE}`;
export const PUBLIC_CONTACT_EMAIL = "contact@helmcontrol.online";
export const PUBLIC_CONTACT_MAILTO = `mailto:${PUBLIC_CONTACT_EMAIL}`;
export const FOUNDED_DATE = "September 2026";
export const COMPANY_LOCATION = "BGC, Taguig, Philippines";
export const WHAT_HELM_IS =
  "Helm brings together what is happening across your company (money, sales, people, and day-to-day work) in one place, so you do not have to bounce between five tools or chase three people for a status update. It shows what needs a decision from you, lets you hand off what does not, and keeps a simple record of what happened.";
export const ABOUT_PROBLEM =
  "Operators running companies of this size still get the day's reality as scattered emails and one-off files: inventory counts, input prices, shipment updates, and more. Opening each one is work. Seeing them together is usually impossible. Helm exists to close that gap.";
export const FOUNDER_NOTE =
  "Tansher Dhawan built Helm himself: he writes the code and still does the day-to-day department redesigns and fixes. There is no separate product team behind the curtain. What you see in the cockpit is what he is actively shipping.";

export const HERO_SUB =
  "Helm gives owners one clear view of money, people, work, and decisions. Open it whenever you need signal: see what changed, make the call, and get back to running the business.";

export const MISSION =
  "Helm exists so a CEO can open one place and see what the business is actually saying today: money, pipeline, people, and the work in motion, without reconstructing that picture from inboxes and attachments every morning.";

export const VISION =
  "The near direction is practical, not abstract: make that morning picture cover every department lane operators already run in Helm (reports, production, procurement, legal, and the rest) so scattered email files stop being the system of record.";
export const ABOUT_DIFFERENTIATOR =
  "Ask Helm answers from the company's live financials and pipeline in the workspace, not from a generic chart library or the public internet. When a figure has not been entered yet, it is instructed to say it does not have that information rather than invent a number.";

export const ABOUT_STORY =
  "Helm started by watching a real manufacturing company get buried in 10+ scattered daily reports by email: inventory counts, commodity and input prices, shipment updates, and other one-off files that were never the same template twice. There was no single place to read them together or in context, only attachments to open one by one. The first real feature work, the Reports Digest, came directly from that problem: upload the day's files and get one readable synthesis instead of another tab marathon. Helm grew from that observed gap into a cockpit for money, decisions, and department work, not from an invented persona.";

export const VALUES = [
  {
    title: "Signal over noise",
    body: "The Briefing and Decision Center are built around what changed, what needs a call, and what can be handed off. Screens exist to help you decide or delegate, not to keep you scrolling.",
  },
  {
    title: "Quiet control",
    body: "Helm does not run engagement loops or notification spam. You open the cockpit when you need the picture; the product is not designed to chase your attention through the day.",
  },
  {
    title: "Honest synthesis",
    body: "On Financials, missing cash, MRR, burn, or runway show as \"Add data,\" not $0. Ask Helm and other synthesis paths are told the same rule: unknown is unknown. Helm would rather admit a gap than invent a confident wrong number.",
  },
];

export const WHO_HELM_IS_FOR = [
  {
    title: "CEOs of companies up to 50",
    body: "You're still in the weeds but shouldn't be drowning in them. Helm gives you a clear view to share with your leadership team without hiring a chief of staff.",
  },
  {
    title: "Owner-operators & traditional businesses",
    body: "Manufacturing, services, agencies, family companies. Helm is a cockpit for running the operation, not a tool only venture-backed startups use.",
  },
  {
    title: "Leadership teams",
    body: "From a handful of people to fifty. Finance, sales, ops, and production keep their lanes. You get one synthesized view.",
  },
];

export const CEO_DAY = [
  { title: "Briefing", body: "Three columns: what changed, what to decide, what to delegate, plus AI synthesis from your live data, and important Gmail threads with AI draft replies you review before sending." },
  { title: "Decision Center", body: "Pending approvals ranked by impact. Helm recommends which to tackle first and why." },
  { title: "Ask Helm", body: "\"What's our biggest risk this quarter?\" answered from your financials and pipeline, not the internet." },
  { title: "CEO Pack", body: "A summary of growth, cash, team pulse, and open decisions, generated in one click, ready to share with your leadership team." },
];

export const PRICING_FAQ = [
  { q: "Is there a free plan?", a: "Yes. Free includes 3 seats, 5 free AI extracts to try it (then upgrade), Ask Helm (10 messages/month), and the AI briefing. Paid plans add monthly extract quotas, more seats, and QuickBooks." },
  { q: "Is there a free trial?", a: "Yes. Starter, Growth, and Business include a 7-day free trial. Cancel before it ends and you won't be charged." },
  { q: "Can my leadership team use Helm?", a: "Yes. Free supports up to 3 members, Starter up to 10, Growth up to 25, and Business up to 50, with role-based access packs." },
  { q: "What integrations are included?", a: "Paid plans can connect Google Calendar and QuickBooks. Free stays manual-only." },
  { q: "Can I cancel anytime?", a: "Yes. Manage billing through Paddle. Cancellation takes effect at the end of the current billing period. No refunds after payment. Use the trial to evaluate." },
];

export const FEATURE_CATEGORIES = [
  {
    id: "intelligence",
    label: "Executive intelligence",
    intro: "AI grounded in your company, not generic chatbot answers.",
    modules: ["Briefing", "Decision Center", "Ask Helm", "CEO Pack", "Gmail thread surfacing + AI draft replies"],
  },
  {
    id: "finance",
    label: "Finance & growth",
    intro: "Pipeline and financials are connected: won deals land as revenue, not a spreadsheet chase.",
    modules: ["Won deals become revenue", "Deal ownership & follow-ups", "Telemetry"],
  },
  {
    id: "operations",
    label: "Production, procurement & maintenance",
    intro: "Not three separate trackers. When production is blocked, Helm shows you exactly why, and jumps that item to the top of whichever queue is holding it up.",
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
    intro: "Team access, department lanes, and integrations. Everyone contributes, you stay in control.",
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
    body: "What needs your attention lives across Slack, the CRM, the finance sheet, the floor, and six dashboards. Nobody has the whole picture, least of all you.",
  },
  {
    title: "You react instead of lead",
    body: "By the time a problem reaches you, it's already a fire. Cash, delivery, and overload creep up silently between check-ins.",
  },
  {
    title: "Dashboards ≠ decisions",
    body: "More charts don't help. You need synthesis: the one number that moved, the one call to make, the one thing to hand off.",
  },
];

export const HOW_IT_WORKS = [
  { n: "01", title: "Your team updates the work", body: "Finance, sales, operations, and other departments use their own simple queues. Connect QuickBooks and Google where useful." },
  { n: "02", title: "Helm prepares your briefing", body: "Money, work, blockers, and open decisions are put in one short briefing. Missing information is called out plainly." },
  { n: "03", title: "You decide and hand off", body: "Approve, follow up, or assign the next step. Helm keeps the owner and outcome visible so decisions do not disappear." },
];

export const FEATURE_HIGHLIGHTS = [
  { title: "Briefing", body: "What changed, what to decide, what to delegate, synthesized from your live company data." },
  { title: "Decision Center", body: "Approvals with AI recommendations and confidence scores, plus outcome checks." },
  { title: "Runway & Burn", body: "Revenue, expenses, and cash tracking. Always know where the money stands." },
  { title: "Ask Helm", body: "Your executive AI chief-of-staff, grounded in your live company data." },
];

/** Department lanes — enable only what the company actually uses. */
export const DEPARTMENTS_SECTION = {
  label: "Departments",
  title: "Turn on only the departments your company actually needs.",
  intro:
    "Give each team its own lane (Procurement, Production, Accounting & Finance, Sales, Legal, HR, Engineering & Maintenance) while you see everything from the top. Disable what you don't use.",
  items: [
    {
      name: "Procurement",
      icon: "package",
      body: "A purchase request queue: requested, approved, ordered, delivered. Each request moves on its own.",
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
      body: "Deal pipeline by stage: open value and wins roll straight into the briefing.",
    },
    {
      name: "Legal",
      icon: "scale",
      body: "A matter queue for contracts and reviews, from draft through signed and filed, with documents attached.",
    },
    {
      name: "HR",
      icon: "users",
      body: "Per-hire onboarding from a reusable template. Each new hire gets their own checklist with assignees.",
    },
    {
      name: "Engineering & Maintenance",
      icon: "wrench",
      body: "A ticket queue for equipment: reported, diagnosed, in repair, resolved. Assign a technician and track it.",
    },
  ],
};

export const FEATURE_MODULES = [
  {
    title: "Briefing",
    ceoValue: "Know what changed and what needs you whenever you open Helm.",
    body: "Three columns: what changed, what to decide, what to delegate, plus AI synthesis when you need the full picture.",
    example: "Revenue is ahead of plan, but engineering capacity risk is rising. Approve the infra reservation.",
  },
  {
    title: "Decision Center",
    ceoValue: "Every open decision, ranked by impact.",
    body: "Approve, follow up, or delegate with AI confidence scores. Helm tracks whether outcomes actually landed.",
    example: "Six pending approvals. Helm recommends the $40K reservation first: 4.2-month payback.",
  },
  {
    title: "Won deals become revenue",
    ceoValue: "Close the deal once. Financials and production follow.",
    body: "Moving a deal to won logs the revenue automatically and offers a production work order from the same deal, so pipeline and financials stay linked.",
    example: "Acme Enterprise closes at $25k. Revenue appears in Financials; Helm asks if you want a work order started.",
  },
  {
    title: "Deal ownership & follow-ups",
    ceoValue: "Real owners, planned next steps, not free-text ghosts.",
    body: "Deals link to Sales teammates, with next-step and follow-up dates so quiet deals surface before they stall.",
    example: "Riley owns the negotiation. Call-back Thursday is on the card, and Helm reminds before it slips.",
  },
  {
    title: "Telemetry",
    ceoValue: "Live KPIs: signal over noise.",
    body: "Headcount, open tasks, MRR, and burn in one view. No digging through five dashboards.",
    example: "MRR up 8% MoM. Open tasks down. One team member overloaded.",
  },
  {
    title: "Ask Helm",
    ceoValue: "Your executive chief-of-staff, on call.",
    body: "Ask anything about your company, grounded in live workspace data, not generic AI.",
    example: "What's our biggest risk this quarter? Helm answers from your actual financials and pipeline.",
  },
  {
    title: "CEO Pack",
    ceoValue: "Leadership synthesis in one click.",
    body: "A plain-English update covering what happened, what needs attention, and what to do next, ready for your leadership team.",
    example: "Financial snapshot, team updates, and open decisions, formatted to forward, not rebuilt in slides.",
  },
  {
    title: "Gmail thread surfacing + AI draft replies",
    ceoValue: "Inbox signal without living in email.",
    body: "Surfaces important Gmail threads in the cockpit and drafts replies you can send, grounded in company context, not a blank compose box.",
    example: "A customer thread needs a decision. Helm drafts the reply; you edit and send.",
  },
  {
    title: "Work order tracking",
    ceoValue: "Production status without a separate system.",
    body: "Work orders move through a fixed flow: Awaiting Materials, In Production, Quality Check, Completed, with overdue detection and average cycle time.",
    example: "Three orders awaiting materials. One past due. Average cycle time visible without a spreadsheet.",
  },
  {
    title: "Vendor memory",
    ceoValue: "Re-order without starting from scratch.",
    body: "Procurement remembers past vendors and prices per item, tracks expected delivery, and flags overdue requests by priority.",
    example: "Same bracket as last quarter. Helm recalls the vendor and last price when you raise the request.",
  },
  {
    title: "Equipment reliability alerts",
    ceoValue: "Notice the machine that keeps coming back.",
    body: "Maintenance tickets for equipment issues, plus reliability alerts when the same machine repeats, and ticket-open downtime totals.",
    example: "Press #3 logged three tickets in 90 days. Helm flags it before the next breakdown.",
  },
  {
    title: "Cross-department blocking",
    ceoValue: "See why production is stuck, in one place.",
    body: "A blocked work order shows the part still in transit or the machine still in repair, and that item jumps to the top of its queue automatically.",
    example: "WO-441 blocked on a bearing order and a mill repair. Both sit at the top of Procurement and Maintenance.",
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
    body: "Role-based packs plus per-department access. Turn on only the departments you need. Each team works in its own lane; you see everything from the top.",
    example: "Your plant lead owns Production. Purchasing runs the request queue. You still see the synthesis in the briefing.",
  },
];

/** Public Help page: plain-language orientation for first-time users. */
export const HOW_TO_USE_INTRO = {
  title: "How to use Helm",
  subtitle: "A plain guide for owners and teammates who are new here.",
  lead:
    "Helm brings together what is happening across your company (money, sales, people, and day-to-day work) in one place, so you do not have to bounce between five tools or chase three people for a status update. It shows what needs a decision from you, lets you hand off what does not, and keeps a simple record of what happened.",
};

export const HOW_TO_USE_AUDIENCES = [
  {
    title: "If you own or run this company",
    body:
      "Start with Briefing, then Decisions. Use Financials and Telemetry when you need the numbers, invite people in Team & Access, and turn on only the Departments your company actually uses.",
  },
  {
    title: "If you were invited to a team",
    body:
      "Start with My Day for your own notes and tasks. You will also see the department pages you belong to (for example Procurement or Production). Seeing only your lanes is intentional: access follows the departments and permissions your owner set, not a hidden lockout.",
  },
];

export const HOW_TO_USE_CONCEPTS = [
  {
    term: "Briefing",
    explanation:
      "Briefing is Helm's homepage for leadership. It pulls together what changed recently, what still needs a call from you, and what you could hand off. Open it when you want the company picture without opening every other tool.",
    example:
      "You open Briefing and see cash was updated, two deals moved stage, and one approval is waiting. You handle the approval and leave the rest for later.",
  },
  {
    term: "My Day",
    explanation:
      "My Day is your personal workspace inside Helm. It holds private sticky notes, your tasks, and an optional team update you can share. Every teammate gets My Day, not only the owner.",
    example:
      "Before a busy afternoon you jot three priorities on private notes, check your open tasks, and post a short team update so others know what you are focused on.",
  },
  {
    term: "Decisions",
    explanation:
      "In Helm, a Decision is a specific call that needs approval, rejection, or a clear owner, not just a vague to-do. Decision Center collects those calls, can draft suggestions from live company data, and keeps resolved items visible so you can see what landed.",
    example:
      "A budget request shows up as a Decision. You approve it, or you delegate it to your finance lead. Later it appears under recently resolved so it does not disappear after you act.",
  },
  {
    term: "Departments",
    explanation:
      "Departments are optional work lanes such as Procurement, Production, Legal, HR, or Maintenance. An owner turns on only what the company uses. Each enabled department gets its own queue so that team can move work without cluttering everyone else's screen.",
    example:
      "You enable Procurement and Production. Purchasing lives in Procurement; shop-floor work orders live in Production. People only see the lanes they are on.",
  },
  {
    term: "Ask Helm",
    explanation:
      "Ask Helm is a question box grounded in your live workspace data. You type a question in plain language and get an answer from what Helm already knows about the company, not from a generic internet chatbot.",
    example:
      "You ask \"What is stuck in procurement?\" and Helm answers from open purchase requests and blockers, instead of giving generic advice.",
  },
  {
    term: "Telemetry",
    explanation:
      "Telemetry is a snapshot of key company numbers and risks in one place: things like headcount, open work, revenue, and cash when you have access. It is for a quick read of the state of the company, not for day-to-day data entry.",
    example:
      "Before a leadership meeting you open Telemetry to confirm headcount, open tasks, and runway without digging through separate spreadsheets.",
  },
  {
    term: "Financials",
    explanation:
      "Financials is where revenue, expenses, and cash are logged so Helm can show MRR, burn, and runway elsewhere in the cockpit. Your finance team (or anyone granted access) can enter numbers manually, import a CSV, or connect accounting tools when available.",
    example:
      "Finance logs this month's expenses and updates cash. Briefing and Telemetry then reflect the new runway without a separate spreadsheet chase.",
  },
  {
    term: "Reports",
    explanation:
      "Reports is where you store written context and generate a shareable CEO Pack. The pack is a plain-English update covering financials, team pulse, and open decisions that you can forward to leadership.",
    example:
      "You add a short sales recap, then generate a CEO Pack and send that one document instead of rebuilding slides from five sources.",
  },
  {
    term: "Team & Access",
    explanation:
      "Team & Access is where owners invite people and choose what each person can do. Access packs set a baseline (for example Finance or Member), and owners can also grant specific areas like Financials or Decisions to individuals.",
    example:
      "You invite your CFO on the Finance pack and grant your ops lead access to Decisions, so they can act without seeing every other restricted area.",
  },
  {
    term: "Integrations",
    explanation:
      "Integrations connect outside tools such as Google Calendar or QuickBooks so Helm can pull events and accounting data automatically. Nothing requires an integration: you can enter the same information manually if you prefer.",
    example:
      "You connect Google Calendar so meetings show in Helm, while expenses keep being entered by hand until QuickBooks is ready.",
  },
];

export const HOW_TO_USE_STEPS = [
  {
    title: "Open Briefing",
    body:
      "Go to Briefing (shown as /app once you are signed in). This is Helm's homepage: what changed, what needs a decision, and what you could hand off. Start sessions here when you want the company picture first.",
    audience: "everyone",
  },
  {
    title: "Act on one Decision",
    body:
      "Open Decisions (/app/decisions). Pick one item that needs a call, then approve it, reject it, or assign a clear owner. Helm keeps the result in recently resolved so the call does not vanish after you act.",
    audience: "everyone",
  },
  {
    title: "Learn My Day and your department lane",
    body:
      "Open My Day (/app/me) for private notes and your tasks. If you belong to a department, open that lane next and move one real item forward. Invited teammates can stop here for a solid first pass.",
    audience: "everyone",
  },
  {
    title: "Connect an integration (owners and admins)",
    body:
      "If you manage the workspace, open Settings and go to Integrations, then connect Google Calendar, QuickBooks, or another available tool when it helps. Skip this if you are an invited teammate without that access, or if your company prefers manual entry for now.",
    audience: "owner",
  },
  {
    title: "Invite a teammate (owners)",
    body:
      "In Team & Access (/app/members), invite someone who should contribute, pick an access pack, and grant only the sections they need. They will land in My Day and their department lanes rather than seeing every owner screen by default.",
    audience: "owner",
  },
  {
    title: "Generate a CEO Pack (owners and report access)",
    body:
      "Open Reports (/app/reports) and generate a CEO Pack when you need a shareable leadership update. This step is for owners and people with report access; department teammates usually will not see it.",
    audience: "owner",
  },
];

export const HOW_TO_USE_FAQ = [
  {
    q: "Why can't I see Financials or Telemetry?",
    a:
      "Those screens are restricted on purpose. Owners always have them. Finance packs can open Financials, and some packs (such as Executive or Operations) can open Telemetry. Everyone else only sees them if an owner grants that section in Team & Access. If a screen is missing, ask your owner for access rather than assuming Helm is broken.",
  },
  {
    q: "What if my company doesn't use QuickBooks or Google Calendar?",
    a:
      "That is fine. Helm works with manual entry everywhere an integration is not connected. Connect tools when they help; nothing in the product requires them to get value from Briefing, Decisions, or department queues.",
  },
  {
    q: "What happens after I approve or delegate a decision in Decision Center?",
    a:
      "The decision moves out of the open queue. Approved, rejected, and delegated items stay visible under recently resolved so you can confirm the outcome and who owns the follow-through. Delegating to yourself keeps the item open so you can still approve or reject it.",
  },
  {
    q: "What's the difference between asking Ask Helm and checking Decisions?",
    a:
      "Ask Helm answers a question you type right now, using your live company data. Decisions is the queue of calls that already need approval or judgment, including suggestions Helm drafts for you to confirm. Use Ask Helm when you have a specific question; use Decisions when something is waiting on a yes, no, or owner.",
  },
  {
    q: "Who can see what I write in My Day?",
    a:
      "Private sticky notes on My Day are only visible to you. They are stored per user and are not shown to teammates or the owner. The optional team update on My Day is different: if you post one, it is shared with the team. Tasks you create or are assigned to follow normal task visibility for people who can see that work.",
  },
  {
    q: "I'm in one department. Why don't I see the rest of the company?",
    a:
      "Access follows department membership and the permissions your owner set. You see My Day plus the department lanes you belong to. Company-wide screens such as Financials, Telemetry, or Team & Access appear only when your pack or an explicit grant includes them. That keeps each team in its own lane while leadership keeps the full picture.",
  },
];

/** Quick-reference paths for people who already know the concepts above. */
export const HOW_TO_USE_MODULES = [
  { nav: "Briefing", path: "/app", tip: "Company homepage: what changed, what to decide, what to hand off." },
  { nav: "My Day", path: "/app/me", tip: "Your private notes, tasks, and optional team update." },
  { nav: "Decisions", path: "/app/decisions", tip: "Approve, reject, or assign ownership; review what already resolved." },
  { nav: "Ask Helm", path: "/app/ask", tip: "Ask a question about your live company data." },
  { nav: "Telemetry", path: "/app/telemetry", tip: "One-screen snapshot of key numbers and risks (access required)." },
  { nav: "Financials", path: "/app/financials", tip: "Log revenue, expenses, and cash (access required)." },
  { nav: "Pipeline", path: "/app/sales", tip: "Deal stages and open pipeline value." },
  { nav: "Reports", path: "/app/reports", tip: "Written context and shareable CEO Pack." },
  { nav: "Departments", path: "/app/settings", tip: "Turn on Procurement, Production, Legal, HR, and more." },
  { nav: "Team & Access", path: "/app/members", tip: "Invite people and choose what each person can open." },
  { nav: "Integrations", path: "/app/integrations", tip: "Now under Settings → Integrations. Optional connections such as Google Calendar or QuickBooks." },
];
