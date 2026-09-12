import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight, Sun, GitBranch, DollarSign, MessageSquareText, Check,
} from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import {
  TAGLINE, CATEGORY, AUDIENCE, HERO_SUB,
  PLANS, PRODUCT_FACTS, HOW_IT_WORKS, FEATURE_HIGHLIGHTS, CEO_DAY, PRICING_FAQ,
} from "@/lib/marketingCopy";
import DepartmentsShowcase from "@/components/marketing/DepartmentsShowcase";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.08 } }),
};

const FEATURE_ICONS = [Sun, GitBranch, DollarSign, MessageSquareText];

function BriefingPreview() {
  return (
    <div className="relative rounded-2xl border border-helm-cream/10 bg-helm-ink-card p-5 md:p-7 border-l-4 border-l-helm-gold">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-helm-gold">Monday · Morning Briefing</p>
        <span className="text-[10px] text-helm-slate">Live workspace data</span>
      </div>
      <p className="text-helm-cream text-xl md:text-2xl font-medium mt-5 leading-snug">Good morning, Alex.</p>
      <p className="text-helm-slate text-sm mt-2 leading-relaxed">Revenue is ahead of plan. Engineering capacity needs a decision today.</p>
      <div className="grid grid-cols-3 gap-2 mt-6 border-y border-helm-cream/10 py-4">
        {[
          ["Monthly revenue", "$248K", "Up $12K this month"],
          ["Cash runway", "17 months", "No change"],
          ["Monthly burn", "$182K", "Down $8K this month"],
        ].map(([l, v, change]) => (
          <div key={l}>
            <p className="text-[9px] font-mono uppercase tracking-wider text-helm-slate">{l}</p>
            <p className="font-mono text-helm-cream text-base mt-1 font-medium">{v}</p>
            <p className="mt-1 text-[10px] text-helm-slate">{change}</p>
          </div>
        ))}
      </div>
      <div className="mt-5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-helm-gold">One decision today</span>
        <p className="mt-2 text-sm text-helm-cream/80 leading-snug">Approve the $40K infrastructure reservation. It pays back in four months and cuts cloud spend by 18%.</p>
        <p className="mt-4 text-xs font-medium text-helm-gold">Review decision →</p>
      </div>
    </div>
  );
}

export default function Landing() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="min-h-screen bg-helm-ink text-helm-cream overflow-x-hidden relative">
      <MarketingNav authed={authed} onEnter={enter} active="/" />

      {/* Hero — flat ink background, no radial glow */}
      <section className="relative z-10 px-6 pt-36 md:pt-44 pb-20 bg-helm-ink">
        <div className="relative mx-auto max-w-6xl grid lg:grid-cols-[1.04fr_0.96fr] gap-14 lg:gap-14 items-center">
          <div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={0}
              className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">{CATEGORY}</motion.p>
            <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
              className="font-display mt-6 text-4xl sm:text-5xl lg:text-6xl font-medium tracking-[-0.02em] leading-[1.08] text-helm-cream">
              {TAGLINE.split(". ").map((part, i, arr) => (
                <span key={part}>
                  {part}{i < arr.length - 1 ? "." : ""}
                  {i < arr.length - 1 && <br />}
                </span>
              ))}
            </motion.h1>
            <motion.p variants={fade} initial="hidden" animate="show" custom={2}
              className="mt-6 text-lg text-helm-slate leading-relaxed max-w-xl">{HERO_SUB}</motion.p>
            <motion.div variants={fade} initial="hidden" animate="show" custom={3} className="mt-9 flex flex-wrap items-center gap-3 relative z-10">
              <button data-testid="hero-cta-btn" onClick={enter} type="button"
                className="group inline-flex items-center gap-2 rounded-lg bg-helm-gold text-helm-navy font-medium px-6 py-3 transition-colors hover:bg-gold-hover">
                {authed ? "Open your cockpit" : "Start free"}
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              <a href="#how" className="inline-flex items-center gap-2 rounded-lg border border-helm-cream/15 px-6 py-3 text-sm text-helm-cream transition-colors hover:border-helm-gold/50">
                See the 3-minute workflow
              </a>
            </motion.div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={4} className="mt-6 text-xs text-helm-slate">{AUDIENCE}</motion.p>
            <motion.p variants={fade} initial="hidden" animate="show" custom={5} className="mt-3 text-xs text-helm-slate">
              <Link to="/security" className="text-helm-slate hover:text-helm-gold transition-colors">
                How Helm protects company data →
              </Link>
            </motion.p>
          </div>
          <motion.div initial={{ opacity: 0, y: 30, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.9, ease, delay: 0.25 }}>
            <BriefingPreview />
          </motion.div>
        </div>
      </section>

      <section className="relative z-10 px-6 py-12 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-6xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-y-8 gap-x-6">
            {PRODUCT_FACTS.map((s, i) => (
              <motion.div key={s.l} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true }} className="text-center">
                <p className="font-mono text-3xl md:text-4xl text-helm-cream">{s.v}</p>
                <p className="mt-2 text-xs text-helm-slate leading-snug">{s.l}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-6 py-24 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }} className="max-w-2xl">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">A day with Helm</p>
            <h2 className="font-display mt-4 text-3xl md:text-4xl font-medium tracking-tight leading-snug">From morning briefing to weekly update.</h2>
          </motion.div>
          <div className="mt-14 space-y-0 border-t border-helm-cream/[0.06]">
            {CEO_DAY.map((step, i) => (
              <motion.div key={step.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                className="grid sm:grid-cols-[7rem_1fr] gap-3 sm:gap-8 py-6 border-b border-helm-cream/[0.06]">
                <p className="font-mono text-[10px] uppercase tracking-wider text-helm-gold pt-1">{step.time}</p>
                <div>
                  <h3 className="text-helm-cream font-medium">{step.title}</h3>
                  <p className="mt-1.5 text-sm text-helm-slate leading-relaxed max-w-xl">{step.body}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="px-6 py-24 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }} className="max-w-2xl">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">How Helm works</p>
            <h2 className="font-display mt-4 text-3xl md:text-4xl font-medium tracking-tight">One short operating rhythm.</h2>
          </motion.div>
          <div className="mt-16 grid md:grid-cols-3 gap-10 md:gap-8">
            {HOW_IT_WORKS.map((s, i) => (
              <motion.div key={s.n} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}>
                <p className="font-mono text-helm-gold/70 text-sm">{s.n}</p>
                <h3 className="mt-4 text-xl text-helm-cream tracking-tight">{s.title}</h3>
                <p className="mt-2 text-sm text-helm-slate leading-relaxed">{s.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-6 py-24 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">Inside the cockpit</p>
            <h2 className="font-display mt-4 text-3xl md:text-4xl font-medium tracking-tight max-w-2xl leading-tight">Everything a CEO needs — nothing they don&apos;t.</h2>
          </motion.div>
          <div className="mt-14 grid lg:grid-cols-2 gap-8">
            {FEATURE_HIGHLIGHTS.map((f, i) => {
              const Icon = FEATURE_ICONS[i];
              const lead = i === 0;
              return (
                <motion.div key={f.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                  className={lead ? "lg:col-span-2 border-b border-helm-cream/[0.06] pb-8" : "pt-1"}>
                  <div className={lead ? "max-w-2xl" : ""}>
                    <div className="flex items-center gap-3 mb-3">
                      <Icon className="w-5 h-5 text-helm-gold shrink-0" />
                      <h3 className="text-lg text-helm-cream tracking-tight">{f.title}</h3>
                    </div>
                    <p className={`text-sm text-helm-slate leading-relaxed ${lead ? "text-base max-w-xl" : ""}`}>{f.body}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
          <div className="mt-10">
            <Link to="/features" className="inline-flex items-center gap-2 text-sm text-helm-gold hover:underline">
              See all features <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      <DepartmentsShowcase />

      <section id="pricing" className="px-6 py-24 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }} className="mb-12 max-w-2xl">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">Pricing</p>
            <h2 className="font-display mt-4 text-3xl md:text-4xl font-medium tracking-tight">Plans that scale with you</h2>
            <p className="mt-3 text-helm-slate">Start free. Paid plans include a 7-day trial. Cancel anytime.</p>
          </motion.div>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.id}
                variants={fade}
                custom={i}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true }}
                className={`rounded-2xl border p-6 flex flex-col ${
                  plan.highlighted
                    ? "border-helm-gold/50 bg-helm-ink-card"
                    : "border-helm-cream/10 bg-helm-ink-card/50"
                }`}
              >
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-helm-gold">{plan.label}</p>
                <p className="font-mono text-4xl text-helm-cream mt-3">
                  {plan.price === 0 ? "$0" : `$${plan.price}`}
                  {plan.price > 0 && <span className="text-base text-helm-slate">/mo</span>}
                </p>
                <p className="text-sm text-helm-slate mt-2 min-h-[2.5rem]">{plan.for}</p>
                {plan.trialDays > 0 && (
                  <p className="text-[11px] font-mono text-helm-gold/80 mt-1">{plan.trialDays}-day free trial</p>
                )}
                <div className="mt-5 space-y-2.5 flex-1">
                  {plan.includes.map((f) => (
                    <div key={f} className="flex items-start gap-2 text-sm text-helm-cream/80">
                      <Check className="w-4 h-4 text-helm-gold shrink-0 mt-0.5" /> {f}
                    </div>
                  ))}
                </div>
                <button type="button" onClick={enter} data-testid={`pricing-cta-${plan.id}`}
                  className={`mt-8 w-full rounded-lg font-medium py-3 transition-colors ${
                    plan.highlighted
                      ? "bg-helm-gold text-helm-navy hover:bg-gold-hover"
                      : "border border-helm-cream/10 text-helm-cream hover:bg-helm-cream/5"
                  }`}>
                  {authed ? "Open cockpit" : plan.id === "free" ? "Get started free" : "Start free trial"}
                </button>
              </motion.div>
            ))}
          </div>
          <div className="mt-12 max-w-2xl space-y-4 text-left">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-helm-slate">Common questions</p>
            {PRICING_FAQ.map((item) => (
              <div key={item.q}>
                <p className="text-sm text-helm-cream">{item.q}</p>
                <p className="text-xs text-helm-slate mt-1 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 px-6 py-28 border-t border-helm-cream/[0.05]">
        <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
          className="relative mx-auto max-w-3xl text-center border border-helm-cream/[0.08] bg-helm-ink-card border-t-4 border-t-helm-gold p-12 md:p-16">
          <h2 className="font-display relative text-3xl md:text-5xl font-medium tracking-tight leading-tight">{TAGLINE}</h2>
          <p className="relative mt-5 text-helm-slate">Quiet control for the CEO everyone&apos;s counting on.</p>
          <div className="relative z-10 mt-9">
            <button data-testid="footer-cta-btn" onClick={enter} type="button"
              className="group inline-flex items-center gap-2 rounded-lg bg-helm-gold text-helm-navy font-medium px-7 py-3 transition-colors hover:bg-gold-hover">
              {authed ? "Open your cockpit" : "Get started"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
          </div>
          <div className="relative mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-helm-slate">
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-helm-gold" /> Free to start · 7-day paid trials</span>
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-helm-gold" /> Sign in with Google</span>
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-helm-gold" /> Live in minutes</span>
          </div>
        </motion.div>
      </section>

      <MarketingFooter />
    </div>
  );
}
