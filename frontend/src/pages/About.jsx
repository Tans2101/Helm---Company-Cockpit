import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Target, Eye, Users, BookOpen } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import {
  ABOUT_STORY, AUDIENCE, CATEGORY, FOUNDER_CREDIT, FOUNDER_NOTE, MISSION, PUBLIC_CONTACT_EMAIL, PUBLIC_CONTACT_MAILTO, TAGLINE, VALUES, VISION, WHO_HELM_IS_FOR,
} from "@/lib/marketingCopy";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.08 } }),
};

const DIFFERENTIATORS = [
  { title: "Synthesis, not dashboards", body: "We don't give you more charts — we tell you what moved, why it matters, and what to do about it." },
  { title: "Decisions, not data dumps", body: "Every module points toward a call you need to make or a handoff you need to give. Helm tracks whether outcomes landed." },
  { title: "Quiet control", body: "No noise, no engagement bait, no notification spam. Just the signal a CEO needs to run the company." },
  { title: "CEO-first, always", body: "Your leadership team contributes through role-based access. The briefing, synthesis, and decision queue belong to you." },
];

export default function About() {
  const { authed, enter } = useMarketingAuth();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="min-h-screen bg-helm-ink text-helm-cream overflow-x-hidden">
      <MarketingNav authed={authed} onEnter={enter} active="/about" />

      <section className="px-6 pt-36 md:pt-44 pb-16">
        <div className="mx-auto max-w-3xl">
          <motion.p variants={fade} initial="hidden" animate="show" custom={0}
            className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">{CATEGORY}</motion.p>
          <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
            className="font-display mt-6 text-4xl md:text-5xl font-medium tracking-tight leading-tight">
            Built for CEOs who run the company — not chase it.
          </motion.h1>
          <motion.p variants={fade} initial="hidden" animate="show" custom={2}
            className="mt-6 text-lg text-helm-slate leading-relaxed">
            {MISSION}
          </motion.p>
        </div>
      </section>

      <section className="px-6 py-16 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-4">
              <BookOpen className="w-5 h-5 text-helm-gold" />
              <h2 className="text-2xl font-light tracking-tight">Why we built Helm</h2>
            </div>
            <p className="text-helm-slate leading-relaxed">{ABOUT_STORY}</p>
            <p className="mt-6 text-helm-cream/80 leading-relaxed" data-testid="founder-credit">
              {FOUNDER_NOTE}
            </p>
            <p className="mt-3 font-mono text-xs uppercase tracking-[0.2em] text-helm-gold">{FOUNDER_CREDIT}</p>
            <p className="mt-4 text-sm text-helm-slate">
              <a href={PUBLIC_CONTACT_MAILTO} className="text-helm-gold hover:underline">{PUBLIC_CONTACT_EMAIL}</a>
            </p>
          </motion.div>
        </div>
      </section>

      <section className="px-6 py-16 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl space-y-16">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-4">
              <Target className="w-5 h-5 text-helm-gold" />
              <h2 className="text-2xl font-light tracking-tight">Our mission</h2>
            </div>
            <p className="text-helm-slate leading-relaxed">{MISSION}</p>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-4">
              <Eye className="w-5 h-5 text-helm-gold" />
              <h2 className="text-2xl font-light tracking-tight">Where we're headed</h2>
            </div>
            <p className="text-helm-slate leading-relaxed">{VISION}</p>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="flex items-center gap-3 mb-6">
              <Users className="w-5 h-5 text-helm-gold" />
              <h2 className="text-2xl font-light tracking-tight">Who Helm is for</h2>
            </div>
            <p className="text-helm-slate leading-relaxed mb-8">
              {AUDIENCE} If you're the person everyone counts on — the one who needs the whole picture,
              makes the hard calls, and delegates the rest — Helm is your cockpit.
            </p>
            <div className="grid sm:grid-cols-3 gap-4">
              {WHO_HELM_IS_FOR.map((item) => (
                <div key={item.title} className="rounded-xl border border-helm-cream/[0.06] bg-helm-ink-card/60 p-5">
                  <h3 className="text-sm font-medium text-helm-cream">{item.title}</h3>
                  <p className="mt-2 text-xs text-helm-slate leading-relaxed">{item.body}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <h2 className="text-2xl font-light tracking-tight mb-6">What we believe</h2>
            <div className="space-y-4">
              {VALUES.map((v) => (
                <div key={v.title} className="rounded-xl border border-helm-cream/[0.06] bg-helm-ink-card/40 p-5">
                  <h3 className="text-helm-cream font-medium">{v.title}</h3>
                  <p className="mt-2 text-sm text-helm-slate leading-relaxed">{v.body}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-helm-cream/[0.06] bg-helm-ink-card/60 p-8">
            <h2 className="text-xl font-light tracking-tight text-helm-cream">What makes Helm different</h2>
            <ul className="mt-6 space-y-4 text-sm text-helm-slate">
              {DIFFERENTIATORS.map((d) => (
                <li key={d.title}>
                  <span className="text-helm-cream font-medium">{d.title}.</span> {d.body}
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      </section>

      <section className="px-6 py-20 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">Ready?</p>
          <h2 className="font-display mt-4 text-3xl font-medium tracking-tight">{TAGLINE}</h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button type="button" onClick={enter}
              className="group inline-flex items-center gap-2 rounded-full bg-helm-gold text-helm-navy font-medium px-6 py-3 hover:bg-helm-gold-hover transition-colors">
              {authed ? "Open your cockpit" : "Get started"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
            <Link to="/features"
              className="inline-flex items-center gap-2 rounded-full border border-helm-cream/10 px-6 py-3 text-sm text-helm-cream/80 hover:bg-helm-cream/5 transition-colors">
              See all features
            </Link>
            <Link to="/security"
              className="inline-flex items-center gap-2 rounded-full border border-helm-cream/10 px-6 py-3 text-sm text-helm-cream/80 hover:bg-helm-cream/5 transition-colors">
              How Helm is secured
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
