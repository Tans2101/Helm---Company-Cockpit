import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import {
  ArrowRight,
  Check,
  Cloud,
  CreditCard,
  Database,
  FileCheck2,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  Trash2,
  UserRoundCheck,
} from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 18 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.65, ease, delay: i * 0.08 },
  }),
};

const WHERE_DATA_LIVES = [
  {
    icon: Database,
    title: "MongoDB Atlas",
    body: "Primary company data (workspaces, financials, pipeline, decisions, and team records) lives in a dedicated MongoDB database, not in the browser.",
  },
  {
    icon: Cloud,
    title: "Cloudflare R2",
    body: "Uploaded bills, receipts, and legal files are stored in a private object bucket. Files are not publicly listed and are retrieved with short-lived signed links.",
  },
  {
    icon: UserRoundCheck,
    title: "Clerk",
    body: "Sign-in identity and authentication sessions are handled by Clerk. Helm stores the account details needed to run your workspace, not payment cards.",
  },
  {
    icon: CreditCard,
    title: "Paddle",
    body: "Paid subscriptions go through Paddle as merchant of record. Card numbers never pass through Helm’s application database.",
  },
];

const CONTROLS = [
  {
    icon: KeyRound,
    title: "Credentials encrypted at rest",
    body: "OAuth tokens for Google, QuickBooks, Xero, and HubSpot are encrypted before they are stored. Encryption keys come from protected environment configuration, never from the codebase.",
  },
  {
    icon: UserRoundCheck,
    title: "Access stays in its lane",
    body: "Each workspace is isolated. Role-based packs and department access limit people to the company data and actions they are authorized to use.",
  },
  {
    icon: Cloud,
    title: "Private file storage",
    body: "Uploaded documents stay in a private Cloudflare R2 bucket. Downloads use time-limited signed URLs rather than public file links.",
  },
  {
    icon: FileCheck2,
    title: "Uploads are inspected",
    body: "Helm enforces a 15 MB size cap and checks PDF, PNG, and JPEG file signatures before accepting a document, reducing the risk from disguised or oversized files.",
  },
  {
    icon: ShieldCheck,
    title: "Safer web defaults",
    body: "HTTPS, restrictive browser security headers, protected administrative diagnostics, and no-store API responses reduce exposure in browsers and intermediaries.",
  },
  {
    icon: Trash2,
    title: "Deletion is designed to finish",
    body: "Workspace deletion removes workspace-scoped database records and associated private files. If object storage is unavailable, Helm fails visibly so deletion can be retried instead of silently leaving files behind.",
  },
];

const PRACTICES = [
  "Integration access is opt-in and can be disconnected at any time.",
  "Shared OAuth connections (Google, QuickBooks, Xero, HubSpot) can be used only by the teammate who connected them, or by a workspace owner. Legacy unstamped connections are limited to owners until someone reconnects.",
  "Google is not read-only. The current Connect Google grant includes Calendar read and write, Gmail snippets plus drafts, Sheets export, and Drive files you pick in Helm, not a full mailbox or Drive dump.",
  "Workspaces that connected Google under the original Calendar + Gmail read grant keep that narrower access until an owner reconnects and accepts the wider consent screen.",
  "Payment card details are handled by Paddle, not stored on Helm servers.",
  "Authentication is handled by Clerk using secure session controls.",
  "Sensitive credentials and provider token responses are excluded from application logs.",
  "Uploaded documents are sent to Anthropic only when an AI extract feature needs to process them.",
];

const QUESTIONS = [
  {
    q: "Can other companies see our workspace?",
    a: "No. Queries are scoped to the signed-in workspace. Members of another company cannot read your financials, documents, or decisions.",
  },
  {
    q: "Does Helm store our full email inbox?",
    a: "No. Helm reads Gmail metadata and short snippets (sender, subject, preview, thread link) for the briefing. Full message bodies are not stored as a mailbox archive. If compose access is granted, Helm can create a Gmail draft when you click Draft reply. It does not send mail. You send from Gmail.",
  },
  {
    q: "What Google access does Helm request now?",
    a: "Connect Google currently requests Calendar read and write (Helm can create or update events when you ask), Gmail read for briefing snippets plus gmail.compose for drafts only (not gmail.send), Google Sheets to create a Financials export spreadsheet, and drive.file so you can pick a bill in Drive. Google’s consent screen may label compose as managing drafts and sending; Helm only posts to Gmail’s drafts API. The original grant was Calendar + Gmail read. Reconnect Google to add the write scopes.",
  },
  {
    q: "Who can see uploaded bills and legal files?",
    a: "Authorized people in your workspace. Files sit in a private bucket and are served through short-lived signed links, not public URLs.",
  },
  {
    q: "Is Helm SOC 2 certified?",
    a: "Not yet. We do not claim certifications we have not earned. This page describes the controls that are in the product today.",
  },
];

export default function Security() {
  const { authed, enter } = useMarketingAuth();

  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = "Security at Helm";
  }, []);

  return (
    <div className="min-h-screen overflow-x-hidden bg-helm-ink text-helm-cream">
      <MarketingNav authed={authed} onEnter={enter} active="/security" />

      <main>
        <section className="relative px-6 pb-16 pt-36 md:pb-24 md:pt-44 bg-helm-ink">
          <div className="relative mx-auto max-w-4xl text-center">
            <motion.div
              variants={fade}
              initial="hidden"
              animate="show"
              custom={0}
              className="mx-auto inline-flex items-center gap-2 rounded-full border border-helm-gold/35 bg-helm-gold/12 px-3 py-1.5"
            >
              <LockKeyhole className="h-3.5 w-3.5 text-helm-gold" />
              <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-helm-gold">
                Security at Helm
              </span>
            </motion.div>
            <motion.h1
              variants={fade}
              initial="hidden"
              animate="show"
              custom={1}
              className="font-display mx-auto mt-7 max-w-3xl text-4xl font-medium leading-[1.08] tracking-tight md:text-6xl"
            >
              Your company runs on trust.
              <span className="block text-helm-slate">Helm is built to protect it.</span>
            </motion.h1>
            <motion.p
              variants={fade}
              initial="hidden"
              animate="show"
              custom={2}
              className="mx-auto mt-7 max-w-2xl text-base leading-relaxed text-helm-slate md:text-lg"
            >
              Cash, decisions, documents, and connected systems are the operating picture of a company.
              Helm is designed so that picture stays inside the workspace that owns it, from sign-in through deletion.
            </motion.p>
            <motion.p
              variants={fade}
              initial="hidden"
              animate="show"
              custom={3}
              className="mt-5 font-mono text-[11px] uppercase tracking-[0.18em] text-helm-slate"
            >
              Last updated September 13, 2026
            </motion.p>
          </div>
        </section>

        <section className="border-y border-helm-cream/[0.05] px-6 py-16 md:py-20">
          <div className="mx-auto max-w-5xl">
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-helm-gold">Why this matters</p>
            <h2 className="font-display mt-4 max-w-3xl text-3xl font-medium tracking-tight md:text-4xl">
              Companies cannot treat a cockpit as optional infrastructure.
            </h2>
            <p className="mt-5 max-w-3xl leading-relaxed text-helm-slate">
              Helm holds the numbers leadership uses to decide, the files finance and legal attach,
              and the tokens that connect accounting, CRM, and calendar. That is why security is
              part of the product, not a footnote on a pricing page.
            </p>
          </div>
        </section>

        <section className="px-6 py-20 md:py-24">
          <div className="mx-auto max-w-5xl">
            <div className="max-w-2xl">
              <p className="font-mono text-xs uppercase tracking-[0.28em] text-helm-gold">Where data lives</p>
              <h2 className="font-display mt-4 text-3xl font-medium tracking-tight md:text-4xl">
                Cloudflare is for files. The company record is MongoDB.
              </h2>
              <p className="mt-4 leading-relaxed text-helm-slate">
                Helm is not a Cloudflare database product. Business records sit in MongoDB Atlas.
                Cloudflare R2 holds private uploaded files. Identity and payments use specialized providers.
              </p>
            </div>
            <div className="mt-12 grid gap-4 sm:grid-cols-2">
              {WHERE_DATA_LIVES.map(({ icon: Icon, title, body }, index) => (
                <motion.article
                  key={title}
                  variants={fade}
                  initial="hidden"
                  whileInView="show"
                  viewport={{ once: true, margin: "-40px" }}
                  custom={index}
                  className="rounded-2xl border border-helm-cream/[0.07] bg-helm-ink-card p-6"
                >
                  <Icon className="h-5 w-5 text-helm-gold" />
                  <h3 className="mt-4 text-base font-medium text-helm-cream">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-helm-slate">{body}</p>
                </motion.article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-helm-cream/[0.05] bg-helm-ink px-6 py-20 md:py-28">
          <div className="mx-auto max-w-5xl">
            <div className="max-w-2xl">
              <p className="font-mono text-xs uppercase tracking-[0.28em] text-helm-gold">Layered protection</p>
              <h2 className="font-display mt-4 text-3xl font-medium tracking-tight md:text-4xl">
                Controls across the data lifecycle
              </h2>
              <p className="mt-4 leading-relaxed text-helm-slate">
                No single control carries the whole burden. Helm combines encryption, access boundaries,
                private storage, validation, and deletion that is meant to complete.
              </p>
            </div>

            <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-helm-cream/[0.07] bg-helm-fg/[0.07] md:grid-cols-2">
              {CONTROLS.map(({ icon: Icon, title, body }, index) => (
                <motion.article
                  key={title}
                  variants={fade}
                  initial="hidden"
                  whileInView="show"
                  viewport={{ once: true, margin: "-50px" }}
                  custom={index % 2}
                  className="bg-helm-ink-card p-7 md:p-8"
                >
                  <Icon className="h-5 w-5 text-helm-gold" />
                  <h3 className="mt-5 text-base font-medium text-helm-cream">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-helm-slate">{body}</p>
                </motion.article>
              ))}
            </div>
          </div>
        </section>

        <section className="px-6 py-20 md:py-24">
          <div className="mx-auto grid max-w-5xl gap-12 md:grid-cols-[0.8fr_1.2fr] md:gap-20">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.28em] text-helm-gold">Data boundaries</p>
              <h2 className="font-display mt-4 text-3xl font-medium tracking-tight">
                Clear about where data goes
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-helm-slate">
                Helm is not the only system involved in delivering the product. We identify the providers
                we use and limit each integration to the access needed for its feature.
              </p>
              <Link to="/privacy" className="mt-6 inline-flex items-center gap-2 text-sm text-helm-gold hover:text-helm-gold-hover">
                Read the Privacy Policy <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <ul className="grid gap-3 sm:grid-cols-2">
              {PRACTICES.map((practice) => (
                <li key={practice} className="flex gap-3 rounded-xl border border-helm-cream/[0.06] bg-helm-fg/[0.02] p-4">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-helm-gold/12">
                    <Check className="h-3 w-3 text-helm-gold" />
                  </span>
                  <span className="text-sm leading-relaxed text-helm-slate">{practice}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="border-y border-helm-cream/[0.05] bg-helm-ink px-6 py-20 md:py-24">
          <div className="mx-auto max-w-5xl">
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-helm-gold">Common questions</p>
            <h2 className="font-display mt-4 text-3xl font-medium tracking-tight">What leadership teams ask</h2>
            <div className="mt-10 grid gap-6 md:grid-cols-2">
              {QUESTIONS.map((item) => (
                <div key={item.q} className="rounded-2xl border border-helm-cream/[0.06] bg-helm-ink-card p-6">
                  <h3 className="text-sm font-medium text-helm-cream">{item.q}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-helm-slate">{item.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="px-6 py-20 md:py-24">
          <div className="mx-auto max-w-4xl rounded-2xl border border-helm-cream/[0.07] bg-helm-ink-card p-8 md:p-12">
            <div className="grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.28em] text-helm-gold">Honest security</p>
                <h2 className="font-display mt-4 text-3xl font-medium tracking-tight">
                  Security is ongoing work.
                </h2>
                <p className="mt-4 max-w-2xl text-sm leading-relaxed text-helm-slate">
                  We do not claim certifications we have not earned or promise that any system is
                  invulnerable. We review Helm&apos;s controls, address identified risks, and communicate
                  our current practices plainly.
                </p>
                <p className="mt-4 text-sm text-helm-slate">
                  Found a security concern?{" "}
                  <a className="text-helm-gold hover:underline" href="mailto:contact@helmcontrol.online?subject=Helm%20security%20report">
                    Report it privately
                  </a>
                  .
                </p>
              </div>
              <button
                type="button"
                onClick={enter}
                className="group inline-flex items-center justify-center gap-2 rounded-full bg-helm-gold px-6 py-3 text-sm font-medium text-helm-navy transition-colors hover:bg-helm-gold-hover"
              >
                {authed ? "Open your cockpit" : "Get started securely"}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </button>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
