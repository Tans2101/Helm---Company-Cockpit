import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight, Sparkles, GitBranch, DollarSign, MessageSquareText,
  Layers, Zap, Command, Check,
} from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import {
  TAGLINE, CATEGORY, AUDIENCE, HERO_SUB, MISSION,
  PLANS, PRODUCT_FACTS, PROBLEMS, HOW_IT_WORKS, FEATURE_HIGHLIGHTS,
  WHO_HELM_IS_FOR, CEO_DAY, PRICING_FAQ,
} from "@/lib/marketingCopy";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.08 } }),
};

const FEATURE_ICONS = [Sparkles, GitBranch, DollarSign, MessageSquareText];
const PROBLEM_ICONS = [Layers, Zap, Command];

function BriefingPreview() {
  return (
    <div className="relative rounded-2xl border border-white/[0.08] bg-[#121214]/80 backdrop-blur-xl p-5 md:p-6 shadow-[0_40px_120px_-30px_rgba(0,0,0,0.9)]">
      <div className="absolute -inset-px rounded-2xl pointer-events-none" style={{ boxShadow: "inset 0 0 60px -20px rgba(201,169,98,0.15)" }} />
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold">Monday · Morning Briefing</p>
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
      </div>
      <h3 className="text-white text-lg md:text-xl font-light mt-3 leading-snug">Good morning, Alex.</h3>
      <p className="text-zinc-400 text-sm mt-1.5 leading-relaxed">Revenue is ahead of plan — but engineering capacity risk is rising.</p>
      <div className="grid grid-cols-3 gap-2 mt-4">
        {[["MRR", "$248K"], ["Runway", "17mo"], ["Burn", "$182K"]].map(([l, v]) => (
          <div key={l} className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
            <p className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">{l}</p>
            <p className="font-mono text-white text-base mt-1">{v}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-lg border border-gold/20 bg-gold/[0.05] p-3">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Sparkles className="w-3 h-3 text-gold" />
          <span className="text-[9px] font-mono uppercase tracking-wider text-gold">Decide today</span>
        </div>
        <p className="text-sm text-zinc-200 leading-snug">Approve the $40K infra reservation — pays back in 4 months, cuts cloud 18%.</p>
      </div>
    </div>
  );
}

export default function Landing() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="min-h-screen bg-[#09090b] text-white grain overflow-x-hidden relative">
      <MarketingNav authed={authed} onEnter={enter} active="/" />

      {/* Hero */}
      <section className="relative z-10 px-6 pt-36 md:pt-44 pb-20">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[600px]" style={{ background: "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(201,169,98,0.10), transparent 70%)" }} />
        <div className="relative mx-auto max-w-6xl grid lg:grid-cols-[1.1fr_0.9fr] gap-12 lg:gap-8 items-center">
          <div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={0}
              className="font-mono text-xs uppercase tracking-[0.3em] text-gold">{CATEGORY}</motion.p>
            <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
              className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05]">
              Run the business.<br />Don't chase it.
            </motion.h1>
            <motion.p variants={fade} initial="hidden" animate="show" custom={2}
              className="mt-6 text-lg text-zinc-400 leading-relaxed max-w-xl">{HERO_SUB}</motion.p>
            <motion.div variants={fade} initial="hidden" animate="show" custom={3} className="mt-9 flex flex-wrap items-center gap-3 relative z-10">
              <button data-testid="hero-cta-btn" onClick={enter} type="button"
                className="group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-6 py-3 transition-colors hover:bg-gold-hover">
                {authed ? "Open your cockpit" : "Get started"}
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              <a href="#how" className="inline-flex items-center gap-2 rounded-full border border-white/10 px-6 py-3 text-sm text-zinc-300 transition-colors hover:bg-white/5">
                See how it works
              </a>
            </motion.div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={4} className="mt-6 text-xs text-zinc-600">{AUDIENCE}</motion.p>
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
                <p className="mt-2 text-xs text-zinc-500 leading-snug">{s.l}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Who it's for */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Who it's for</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight max-w-2xl leading-tight">
              Built for the CEO everyone's counting on.
            </h2>
            <p className="mt-4 text-zinc-500 max-w-xl">{AUDIENCE}</p>
          </motion.div>
          <div className="mt-12 grid md:grid-cols-3 gap-5">
            {WHO_HELM_IS_FOR.map((item, i) => (
              <motion.div key={item.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6">
                <h3 className="text-lg text-white tracking-tight">{item.title}</h3>
                <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{item.body}</p>
              </motion.div>
            ))}
          </div>
          <div className="mt-8 text-center">
            <Link to="/about" className="inline-flex items-center gap-2 text-sm text-gold hover:underline">
              Read our story <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* A day with Helm */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }} className="text-center">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">A day with Helm</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">From morning briefing to board prep.</h2>
          </motion.div>
          <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {CEO_DAY.map((step, i) => (
              <motion.div key={step.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-5">
                <p className="font-mono text-[10px] uppercase tracking-wider text-gold">{step.time}</p>
                <h3 className="mt-3 text-white font-medium">{step.title}</h3>
                <p className="mt-2 text-xs text-zinc-500 leading-relaxed">{step.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">The problem</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight max-w-2xl leading-tight">
              You're running the company. So why is it this hard to see it?
            </h2>
          </motion.div>
          <div className="mt-14 grid md:grid-cols-3 gap-5">
            {PROBLEMS.map((p, i) => {
              const Icon = PROBLEM_ICONS[i];
              return (
                <motion.div key={p.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}
                  className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6">
                  <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/10 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-gold" />
                  </div>
                  <h3 className="mt-5 text-lg text-white tracking-tight">{p.title}</h3>
                  <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{p.body}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }} className="text-center">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">How Helm works</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">Synthesis, not another dashboard.</h2>
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

      {/* Pricing */}
      <section id="pricing" className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }} className="text-center mb-12">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Pricing</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">Plans that scale with you</h2>
            <p className="mt-3 text-zinc-500">Start free. Paid plans include a 7-day trial. Cancel anytime.</p>
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
                    ? "border-gold/30 bg-[#121214]/80 shadow-[0_0_40px_-12px_rgba(201,169,98,0.25)]"
                    : "border-white/10 bg-[#121214]/50"
                }`}
              >
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-gold">{plan.label}</p>
                <p className="font-mono text-4xl text-white mt-3">
                  {plan.price === 0 ? "$0" : `$${plan.price}`}
                  {plan.price > 0 && <span className="text-base text-zinc-600">/mo</span>}
                </p>
                <p className="text-sm text-zinc-500 mt-2 min-h-[2.5rem]">{plan.for}</p>
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
                  className={`mt-8 w-full rounded-full font-medium py-3 transition-colors ${
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
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-600 text-center">Common questions</p>
            {PRICING_FAQ.map((item) => (
              <div key={item.q}>
                <p className="text-sm text-white">{item.q}</p>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Mission teaser */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-3xl text-center">
          <motion.p variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="text-lg text-zinc-400 leading-relaxed">{MISSION}</motion.p>
          <Link to="/about" className="mt-6 inline-flex items-center gap-2 text-sm text-gold hover:underline">
            Read our story <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative z-10 px-6 py-28 border-t border-white/[0.05]">
        <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
          className="relative mx-auto max-w-3xl text-center rounded-3xl border border-white/[0.08] bg-[#121214]/60 p-12 md:p-16 overflow-hidden">
          <div className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(ellipse 70% 60% at 50% 0%, rgba(201,169,98,0.12), transparent 70%)" }} />
          <h2 className="relative text-3xl md:text-5xl font-light tracking-tight leading-tight">{TAGLINE}</h2>
          <p className="relative mt-5 text-zinc-400">Quiet control for the CEO everyone's counting on.</p>
          <div className="relative z-10 mt-9">
            <button data-testid="footer-cta-btn" onClick={enter} type="button"
              className="group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-7 py-3 transition-colors hover:bg-gold-hover">
              {authed ? "Open your cockpit" : "Get started"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
          </div>
          <div className="relative mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-zinc-600">
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
