import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import { CATEGORY, FEATURE_MODULES, TAGLINE } from "@/lib/marketingCopy";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.06 } }),
};

export default function Features() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

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
            Each module is designed for one person: the CEO. Here's what you get — and why it matters.
          </motion.p>
        </div>
      </section>

      <section className="px-6 py-12 border-t border-white/[0.05]">
        <div className="mx-auto max-w-4xl space-y-6">
          {FEATURE_MODULES.map((mod, i) => (
            <motion.article key={mod.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }}
              className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6 md:p-8">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold">{mod.ceoValue}</p>
              <h2 className="mt-2 text-xl md:text-2xl font-light tracking-tight text-white">{mod.title}</h2>
              <p className="mt-3 text-sm text-zinc-400 leading-relaxed">{mod.body}</p>
              <p className="mt-4 text-sm text-zinc-500 italic border-l-2 border-gold/30 pl-4">{mod.example}</p>
            </motion.article>
          ))}
        </div>
      </section>

      <section className="px-6 py-20 border-t border-white/[0.05]">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-2xl font-light tracking-tight text-white">{TAGLINE}</p>
          <button type="button" onClick={enter}
            className="mt-8 group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-6 py-3 hover:bg-gold-hover transition-colors">
            {authed ? "Open your cockpit" : "Start with Helm Pro"}
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </button>
          <p className="mt-4 text-sm text-zinc-600">
            <Link to="/#pricing" className="text-zinc-500 hover:text-white transition-colors">View pricing</Link>
          </p>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
