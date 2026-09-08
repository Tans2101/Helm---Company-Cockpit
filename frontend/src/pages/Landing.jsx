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
    <div className="marketing-panel relative border-l-4 border-l-gold p-5 md:p-7">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-gold">Today&apos;s brief · 3 minute read</p>
        <span className="text-[10px] text-zinc-500">Live workspace data</span>
      </div>
      <p className="text-white text-xl md:text-2xl font-medium mt-5 leading-snug">Good morning, Alex.</p>
      <p className="text-zinc-400 text-sm mt-2 leading-relaxed">Revenue is ahead of plan. Engineering capacity needs a decision today.</p>
      <div className="grid grid-cols-3 gap-2 mt-6 border-y border-white/[0.08] py-4">
        {[
          ["Monthly revenue", "$248K", "Up $12K this month"],
          ["Cash runway", "17 months", "No change"],
          ["Monthly burn", "$182K", "Down $8K this month"],
        ].map(([l, v, change]) => (
          <div key={l}>
            <p className="text-[9px] font-mono uppercase tracking-wider text-zinc-400">{l}</p>
            <p className="font-mono text-white text-base mt-1 font-medium">{v}</p>
            <p className="mt-1 text-[10px] text-zinc-500">{change}</p>
          </div>
        ))}
      </div>
      <div className="mt-5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-gold">One decision today</span>
        <p className="mt-2 text-sm text-zinc-300 leading-snug">Approve the $40K infrastructure reservation. It pays back in four months and cuts cloud spend by 18%.</p>
        <p className="mt-4 text-xs font-medium text-gold">Review decision →</p>
      </div>
    </div>
  );
}

export default function Landing() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="marketing-light min-h-screen overflow-x-hidden relative">
      <MarketingNav authed={authed} onEnter={enter} active="/" />

      {/* Hero */}
      <section className="relative z-10 px-6 pt-36 md:pt-44 pb-20 bg-[#f7f6f2]">
        <div className="relative mx-auto max-w-6xl grid lg:grid-cols-[1.04fr_0.96fr] gap-14 lg:gap-14 items-center">
          <div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={0}
              className="font-mono text-xs uppercase tracking-[0.3em] text-gold">{CATEGORY}</motion.p>
            <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
              className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-medium tracking-[-0.045em] leading-[1.02]">
              Know what needs you.<br />Delegate the rest.
            </motion.h1>
            <motion.p variants={fade} initial="hidden" animate="show" custom={2}
              className="mt-6 text-lg text-zinc-400 leading-relaxed max-w-xl">{HERO_SUB}</motion.p>
            <motion.div variants={fade} initial="hidden" animate="show" custom={3} className="mt-9 flex flex-wrap items-center gap-3 relative z-10">
              <button data-testid="hero-cta-btn" onClick={enter} type="button"
                className="marketing-dark-button group inline-flex items-center gap-2 rounded-lg bg-[#18211c] text-white font-medium px-6 py-3 transition-colors hover:bg-[#2b362f]">
                {authed ? "Open your cockpit" : "Start free"}
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              <a href="#how" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white px-6 py-3 text-sm text-zinc-300 transition-colors hover:bg-white/5">
                See the 3-minute workflow
              </a>
            </motion.div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={4} className="mt-6 text-xs text-zinc-400">{AUDIENCE}</motion.p>
          </div>
          <motion.div initial={{ opacity: 0, y: 30, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.9, ease, delay: 0.25 }}>
            <BriefingPreview />
          </motion.div>
        </div>
      </section>

      {/* Product facts */}
      <section className="relative z-10 px-6 py-12 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-y-8 gap-x-6">
            {PRODUCT_FACTS.map((s, i) => (
              <motion.div key={s.l} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true }} className="text-center">
                <p className="font-mono text-3xl md:text-4xl text-white">{s.v}</p>
                <p className="mt-2 text-xs text-zinc-400 leading-snug">{s.l}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* A day with Helm */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }} className="text-center">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">A day with Helm</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">From morning briefing to weekly synthesis.</h2>
          </motion.div>
          <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {CEO_DAY.map((step, i) => (
              <motion.div key={step.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-5">
                <p className="font-mono text-[10px] uppercase tracking-wider text-gold">{step.time}</p>
                <h3 className="mt-3 text-white font-medium">{step.title}</h3>
                <p className="mt-2 text-xs text-zinc-400 leading-relaxed">{step.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }} className="text-center">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">How Helm works</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-medium tracking-tight">One short operating rhythm.</h2>
          </motion.div>
          <div className="mt-16 grid md:grid-cols-3 gap-8">
            {HOW_IT_WORKS.map((s, i) => (
              <motion.div key={s.n} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}>
                <p className="font-mono text-gold/70 text-sm">{s.n}</p>
                <div className="mt-3 h-px w-full bg-gradient-to-r from-gold/40 to-transparent" />
                <h3 className="mt-5 text-xl text-white tracking-tight">{s.title}</h3>
                <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{s.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Inside the cockpit</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight max-w-2xl leading-tight">Everything a CEO needs — nothing they don't.</h2>
          </motion.div>
          <div className="mt-14 grid sm:grid-cols-2 gap-5">
            {FEATURE_HIGHLIGHTS.map((f, i) => {
              const Icon = FEATURE_ICONS[i];
              return (
                <motion.div key={f.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                  className="group rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6 transition-colors hover:border-gold/25">
                  <div className="flex items-start gap-4">
                    <div className="w-11 h-11 rounded-lg bg-gold/10 border border-gold/25 flex items-center justify-center shrink-0">
                      <Icon className="w-5 h-5 text-gold" />
                    </div>
                    <div>
                      <h3 className="text-lg text-white tracking-tight">{f.title}</h3>
                      <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed">{f.body}</p>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
          <div className="mt-10 text-center">
            <Link to="/features" className="inline-flex items-center gap-2 text-sm text-gold hover:underline">
              See all features <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      <DepartmentsShowcase />

      {/* Pricing */}
      <section id="pricing" className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }} className="text-center mb-12">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Pricing</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">Plans that scale with you</h2>
            <p className="mt-3 text-zinc-400">Start free. Paid plans include a 7-day trial. Cancel anytime.</p>
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
                    ? "border-gold/50 bg-[#fffdf6] shadow-[0_18px_45px_-35px_rgba(24,33,28,0.45)]"
                    : "border-white/10 bg-[#121214]/50"
                }`}
              >
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-gold">{plan.label}</p>
                <p className="font-mono text-4xl text-white mt-3">
                  {plan.price === 0 ? "$0" : `$${plan.price}`}
                  {plan.price > 0 && <span className="text-base text-zinc-400">/mo</span>}
                </p>
                <p className="text-sm text-zinc-400 mt-2 min-h-[2.5rem]">{plan.for}</p>
                {plan.trialDays > 0 && (
                  <p className="text-[11px] font-mono text-gold/80 mt-1">{plan.trialDays}-day free trial</p>
                )}
                <div className="mt-5 space-y-2.5 flex-1">
                  {plan.includes.map((f) => (
                    <div key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                      <Check className="w-4 h-4 text-gold shrink-0 mt-0.5" /> {f}
                    </div>
                  ))}
                </div>
                <button type="button" onClick={enter} data-testid={`pricing-cta-${plan.id}`}
                  className={`mt-8 w-full rounded-lg font-medium py-3 transition-colors ${
                    plan.highlighted
                      ? "bg-gold text-black hover:bg-gold-hover"
                      : "border border-white/10 text-white hover:bg-white/5"
                  }`}>
                  {authed ? "Open cockpit" : plan.id === "free" ? "Get started free" : "Start free trial"}
                </button>
              </motion.div>
            ))}
          </div>
          <div className="mt-12 max-w-2xl mx-auto space-y-4 text-left">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400 text-center">Common questions</p>
            {PRICING_FAQ.map((item) => (
              <div key={item.q}>
                <p className="text-sm text-white">{item.q}</p>
                <p className="text-xs text-zinc-400 mt-1 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative z-10 px-6 py-28 border-t border-white/[0.05]">
        <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
          className="marketing-panel relative mx-auto max-w-3xl text-center border-t-4 border-t-gold p-12 md:p-16 overflow-hidden">
          <h2 className="relative text-3xl md:text-5xl font-light tracking-tight leading-tight">{TAGLINE}</h2>
          <p className="relative mt-5 text-zinc-400">Quiet control for the CEO everyone's counting on.</p>
          <div className="relative z-10 mt-9">
            <button data-testid="footer-cta-btn" onClick={enter} type="button"
              className="marketing-dark-button group inline-flex items-center gap-2 rounded-lg bg-[#18211c] text-white font-medium px-7 py-3 transition-colors hover:bg-[#2b362f]">
              {authed ? "Open your cockpit" : "Get started"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
          </div>
          <div className="relative mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-zinc-400">
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-gold" /> Free to start · 7-day paid trials</span>
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-gold" /> Sign in with Google</span>
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-gold" /> Live in minutes</span>
          </div>
        </motion.div>
      </section>

      <MarketingFooter />
    </div>
  );
}
