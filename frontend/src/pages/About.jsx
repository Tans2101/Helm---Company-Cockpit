import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import {
  ABOUT_STORY, AUDIENCE, CATEGORY, FOUNDER_CREDIT, FOUNDER_NOTE,
  PUBLIC_CONTACT_EMAIL, PUBLIC_CONTACT_MAILTO, TAGLINE, VALUES, VISION, WHO_HELM_IS_FOR, MISSION,
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

      <section className="px-6 pt-36 md:pt-48 pb-20">
        <div className="mx-auto max-w-3xl">
          <motion.p variants={fade} initial="hidden" animate="show" custom={0}
            className="font-mono text-xs uppercase tracking-[0.3em] text-helm-slate">{CATEGORY}</motion.p>
          <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
            className="font-display mt-8 text-5xl md:text-6xl font-medium tracking-[-0.03em] leading-[1.05]">
            Built for CEOs who run the company — not chase it.
          </motion.h1>
          <motion.p variants={fade} initial="hidden" animate="show" custom={2}
            className="mt-8 text-lg text-helm-slate leading-relaxed">
            {MISSION}
          </motion.p>
        </div>
      </section>

      <section className="px-6 py-20 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl">
          <div className="h-px w-10 bg-helm-gold mb-6" aria-hidden />
          <h2 className="font-display text-3xl font-medium tracking-tight">Why we built Helm</h2>
          <p className="mt-5 text-helm-slate leading-relaxed">{ABOUT_STORY}</p>
          <p className="mt-8 text-helm-cream/80 leading-relaxed" data-testid="founder-credit">{FOUNDER_NOTE}</p>
          <p className="mt-3 font-mono text-xs uppercase tracking-[0.2em] text-helm-slate">{FOUNDER_CREDIT}</p>
          <p className="mt-4 text-sm text-helm-slate">
            <a href={PUBLIC_CONTACT_MAILTO} className="hover:text-helm-cream transition-colors">{PUBLIC_CONTACT_EMAIL}</a>
          </p>
        </div>
      </section>

      <section className="px-6 py-20 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl space-y-16">
          <div>
            <div className="h-px w-10 bg-helm-gold mb-6" aria-hidden />
            <h2 className="font-display text-3xl font-medium tracking-tight">Our mission</h2>
            <p className="mt-5 text-helm-slate leading-relaxed">{MISSION}</p>
          </div>
          <div>
            <h2 className="font-display text-3xl font-medium tracking-tight">Where we&apos;re headed</h2>
            <p className="mt-5 text-helm-slate leading-relaxed">{VISION}</p>
          </div>
          <div>
            <h2 className="font-display text-3xl font-medium tracking-tight">Who Helm is for</h2>
            <p className="mt-5 text-helm-slate leading-relaxed mb-10">
              {AUDIENCE} If you&apos;re the person everyone counts on — the one who needs the whole picture,
              makes the hard calls, and delegates the rest — Helm is your cockpit.
            </p>
            <div className="border-t border-helm-cream/[0.06]">
              {WHO_HELM_IS_FOR.map((item) => (
                <div key={item.title} className="grid sm:grid-cols-[11rem_1fr] gap-2 sm:gap-8 py-6 border-b border-helm-cream/[0.06]">
                  <h3 className="font-display text-base text-helm-cream tracking-tight">{item.title}</h3>
                  <p className="text-sm text-helm-slate leading-relaxed">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="px-6 py-20 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-3xl space-y-16">
          <div>
            <div className="h-px w-10 bg-helm-gold mb-6" aria-hidden />
            <h2 className="font-display text-3xl font-medium tracking-tight mb-8">What we believe</h2>
            <div className="border-t border-helm-cream/[0.06]">
              {VALUES.map((v) => (
                <div key={v.title} className="py-6 border-b border-helm-cream/[0.06]">
                  <h3 className="font-display text-lg text-helm-cream tracking-tight">{v.title}</h3>
                  <p className="mt-2 text-sm text-helm-slate leading-relaxed">{v.body}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <h2 className="font-display text-3xl font-medium tracking-tight">What makes Helm different</h2>
            <ul className="mt-8 space-y-0 border-t border-helm-cream/[0.06]">
              {DIFFERENTIATORS.map((d) => (
                <li key={d.title} className="py-5 border-b border-helm-cream/[0.06] text-sm text-helm-slate leading-relaxed">
                  <span className="text-helm-cream font-medium">{d.title}.</span> {d.body}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="px-6 py-24 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto h-px w-10 bg-helm-gold mb-8" aria-hidden />
          <h2 className="font-display text-4xl font-medium tracking-tight leading-tight">{TAGLINE}</h2>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <button type="button" onClick={enter}
              className="group inline-flex items-center gap-2 rounded-md bg-helm-cream text-helm-navy font-medium px-6 py-3 hover:bg-helm-gold transition-colors">
              {authed ? "Open your cockpit" : "Get started"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
            <Link to="/features"
              className="inline-flex items-center gap-2 rounded-md border border-helm-cream/15 px-6 py-3 text-sm text-helm-cream/80 hover:border-helm-cream/30 transition-colors">
              See all features
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
