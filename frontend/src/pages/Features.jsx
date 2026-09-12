import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import { CATEGORY, FEATURE_CATEGORIES, FEATURE_MODULES, PRO_FEATURES, TAGLINE } from "@/lib/marketingCopy";
import DepartmentsShowcase from "@/components/marketing/DepartmentsShowcase";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.06 } }),
};

export default function Features() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  const modulesByTitle = Object.fromEntries(FEATURE_MODULES.map((m) => [m.title, m]));

  return (
    <div className="min-h-screen bg-helm-ink text-helm-cream overflow-x-hidden">
      <MarketingNav authed={authed} onEnter={enter} active="/features" />

      <section className="px-6 pt-36 md:pt-44 pb-12">
        <div className="mx-auto max-w-3xl text-center">
          <motion.p variants={fade} initial="hidden" animate="show" custom={0}
            className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">{CATEGORY}</motion.p>
          <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
            className="font-display mt-6 text-4xl md:text-5xl font-medium tracking-tight leading-tight">
            Everything in the cockpit
          </motion.h1>
          <motion.p variants={fade} initial="hidden" animate="show" custom={2}
            className="mt-6 text-lg text-helm-slate leading-relaxed">
            Briefing, decisions, departments, and the rest of the cockpit —
            each designed to answer a specific leadership question:
            what changed, what to decide, what to delegate, and whether it landed.
          </motion.p>
        </div>
      </section>

      {/* All-included strip */}
      <section className="px-6 pb-12">
        <div className="mx-auto max-w-4xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-helm-gold/20 bg-helm-gold/[0.04] p-6 md:p-8">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-helm-gold mb-4">Included in Helm</p>
            <div className="grid sm:grid-cols-2 gap-x-8 gap-y-2">
              {PRO_FEATURES.map((f) => (
                <p key={f} className="text-sm text-helm-cream/80 flex items-start gap-2">
                  <span className="text-helm-gold mt-0.5">✓</span> {f}
                </p>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {FEATURE_CATEGORIES.map((cat, ci) => (
        <section key={cat.id} className="px-6 py-12 border-t border-helm-cream/[0.05]">
          <div className="mx-auto max-w-4xl">
            <motion.div variants={fade} custom={ci} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }} className="mb-8">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-helm-gold">{cat.label}</p>
              <p className="mt-2 text-helm-slate text-sm">{cat.intro}</p>
            </motion.div>
            <div className="space-y-5">
              {cat.modules.map((title, i) => {
                const mod = modulesByTitle[title];
                if (!mod) return null;
                return (
                  <motion.article key={mod.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }}
                    className="rounded-2xl border border-helm-cream/[0.06] bg-helm-ink-card/60 p-6 md:p-8">
                    <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-helm-gold">{mod.ceoValue}</p>
                    <h2 className="mt-2 text-xl md:text-2xl font-light tracking-tight text-helm-cream">{mod.title}</h2>
                    <p className="mt-3 text-sm text-helm-slate leading-relaxed">{mod.body}</p>
                    <p className="mt-4 text-sm text-helm-slate italic border-l-2 border-helm-gold/30 pl-4">{mod.example}</p>
                  </motion.article>
                );
              })}
            </div>
          </div>
        </section>
      ))}

      <DepartmentsShowcase compact />

      <section className="px-6 py-20 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-2xl font-light tracking-tight text-helm-cream">{TAGLINE}</p>
          <p className="mt-3 text-sm text-helm-slate">One plan. Full cockpit. Live in minutes.</p>
          <button type="button" onClick={enter}
            className="mt-8 group inline-flex items-center gap-2 rounded-full bg-helm-gold text-helm-navy font-medium px-6 py-3 hover:bg-gold-hover transition-colors">
            {authed ? "Open your cockpit" : "Get started with Helm"}
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </button>
          <p className="mt-4 text-sm text-helm-slate flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
            <Link to="/#pricing" className="text-helm-slate hover:text-helm-cream transition-colors">View pricing</Link>
            <Link to="/about" className="text-helm-slate hover:text-helm-cream transition-colors">About Helm</Link>
            <Link to="/security" className="text-helm-slate hover:text-helm-cream transition-colors">Security</Link>
          </p>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
