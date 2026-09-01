import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Target, Eye, Users } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import { AUDIENCE, CATEGORY, MISSION, TAGLINE, VISION } from "@/lib/marketingCopy";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.08 } }),
};

export default function About() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="min-h-screen bg-[#09090b] text-white grain overflow-x-hidden">
      <MarketingNav authed={authed} onEnter={enter} active="/about" />

      <section className="px-6 pt-36 md:pt-44 pb-16">
        <div className="mx-auto max-w-3xl">
          <motion.p variants={fade} initial="hidden" animate="show" custom={0}
            className="font-mono text-xs uppercase tracking-[0.3em] text-gold">{CATEGORY}</motion.p>
          <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
            className="mt-6 text-4xl md:text-5xl font-light tracking-tight leading-tight">
            {TAGLINE}
          </motion.h1>
          <motion.p variants={fade} initial="hidden" animate="show" custom={2}
            className="mt-6 text-lg text-zinc-400 leading-relaxed">
            {MISSION}
          </motion.p>
        </div>
      </section>

      <section className="px-6 py-16 border-t border-white/[0.05]">
        <div className="mx-auto max-w-3xl space-y-16">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-4">
              <Target className="w-5 h-5 text-gold" />
              <h2 className="text-2xl font-light tracking-tight">Our mission</h2>
            </div>
            <p className="text-zinc-400 leading-relaxed">{MISSION}</p>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-4">
              <Eye className="w-5 h-5 text-gold" />
              <h2 className="text-2xl font-light tracking-tight">Where we're headed</h2>
            </div>
            <p className="text-zinc-400 leading-relaxed">{VISION}</p>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-5 h-5 text-gold" />
              <h2 className="text-2xl font-light tracking-tight">Who Helm is for</h2>
            </div>
            <p className="text-zinc-400 leading-relaxed">
              Helm is built for <span className="text-white">CEOs and founders</span> running early-stage companies.
              {" "}{AUDIENCE} If you're the person everyone counts on — the one who needs the whole picture,
              makes the hard calls, and delegates the rest — Helm is your cockpit.
            </p>
            <p className="text-zinc-400 leading-relaxed mt-4">
              Your leadership team uses Helm too: finance updates the numbers, sales owns the pipeline,
              ops flags risks. But the briefing, the synthesis, and the decisions — that's yours.
            </p>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-8">
            <h2 className="text-xl font-light tracking-tight text-white">What makes Helm different</h2>
            <ul className="mt-4 space-y-3 text-sm text-zinc-400">
              <li><span className="text-white">Synthesis, not dashboards.</span> We don't give you more charts — we tell you what moved and what to do about it.</li>
              <li><span className="text-white">Decisions, not data dumps.</span> Every module points toward a call you need to make or a handoff you need to make.</li>
              <li><span className="text-white">Quiet control.</span> No noise, no engagement bait. Just the signal a CEO needs to run the company.</li>
            </ul>
          </motion.div>
        </div>
      </section>

      <section className="px-6 py-20 border-t border-white/[0.05]">
        <div className="mx-auto max-w-3xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Ready?</p>
          <h2 className="mt-4 text-3xl font-light tracking-tight">{TAGLINE}</h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button type="button" onClick={enter}
              className="group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-6 py-3 hover:bg-gold-hover transition-colors">
              {authed ? "Open your cockpit" : "Get started"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
            <Link to="/features"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-6 py-3 text-sm text-zinc-300 hover:bg-white/5 transition-colors">
              See all features
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
