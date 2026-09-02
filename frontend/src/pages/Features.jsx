import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import { CATEGORY, FEATURE_CATEGORIES, FEATURE_MODULES, PRO_FEATURES, TAGLINE } from "@/lib/marketingCopy";

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
    <div className="min-h-screen bg-[#09090b] text-white grain overflow-x-hidden">
      <MarketingNav authed={authed} onEnter={enter} active="/features" />

      <section className="px-6 pt-36 md:pt-44 pb-12">
        <div className="mx-auto max-w-3xl text-center">
          <motion.p variants={fade} initial="hidden" animate="show" custom={0}
            className="font-mono text-xs uppercase tracking-[0.3em] text-gold">{CATEGORY}</motion.p>
          <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
            className="mt-6 text-4xl md:text-5xl font-light tracking-tight leading-tight">
            Everything in the cockpit
          </motion.h1>
          <motion.p variants={fade} initial="hidden" animate="show" custom={2}
            className="mt-6 text-lg text-zinc-400 leading-relaxed">
            Twelve modules. One CEO view. Each designed to answer a specific leadership question —
            what changed, what to decide, what to delegate, and whether it landed.
          </motion.p>
        </div>
      </section>

      {/* All-included strip */}
      <section className="px-6 pb-12">
        <div className="mx-auto max-w-4xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-gold/20 bg-gold/[0.04] p-6 md:p-8">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold mb-4">Included in Helm</p>
            <div className="grid sm:grid-cols-2 gap-x-8 gap-y-2">
              {PRO_FEATURES.map((f) => (
                <p key={f} className="text-sm text-zinc-300 flex items-start gap-2">
                  <span className="text-gold mt-0.5">✓</span> {f}
                </p>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {FEATURE_CATEGORIES.map((cat, ci) => (
        <section key={cat.id} className="px-6 py-12 border-t border-white/[0.05]">
          <div className="mx-auto max-w-4xl">
            <motion.div variants={fade} custom={ci} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }} className="mb-8">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold">{cat.label}</p>
              <p className="mt-2 text-zinc-500 text-sm">{cat.intro}</p>
            </motion.div>
            <div className="space-y-5">
              {cat.modules.map((title, i) => {
                const mod = modulesByTitle[title];
                if (!mod) return null;
                return (
                  <motion.article key={mod.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }}
                    className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6 md:p-8">
                    <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold">{mod.ceoValue}</p>
                    <h2 className="mt-2 text-xl md:text-2xl font-light tracking-tight text-white">{mod.title}</h2>
                    <p className="mt-3 text-sm text-zinc-400 leading-relaxed">{mod.body}</p>
                    <p className="mt-4 text-sm text-zinc-500 italic border-l-2 border-gold/30 pl-4">{mod.example}</p>
                  </motion.article>
                );
              })}
            </div>
          </div>
        </section>
      ))}

      <section className="px-6 py-20 border-t border-white/[0.05]">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-2xl font-light tracking-tight text-white">{TAGLINE}</p>
          <p className="mt-3 text-sm text-zinc-500">One plan. Full cockpit. Live in minutes.</p>
          <button type="button" onClick={enter}
            className="mt-8 group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-6 py-3 hover:bg-gold-hover transition-colors">
            {authed ? "Open your cockpit" : "Get started with Helm"}
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </button>
          <p className="mt-4 text-sm text-zinc-600 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
            <Link to="/#pricing" className="text-zinc-500 hover:text-white transition-colors">View pricing</Link>
            <Link to="/about" className="text-zinc-500 hover:text-white transition-colors">About Helm</Link>
          </p>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
