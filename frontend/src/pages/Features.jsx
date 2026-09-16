import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import ProductScreens from "@/components/marketing/ProductScreens";
import DepartmentsShowcase from "@/components/marketing/DepartmentsShowcase";
import { useMarketingAuth } from "@/hooks/useMarketingAuth";
import { goToHomeHash } from "@/lib/marketingHash";
import { CATEGORY, FEATURE_CATEGORIES, FEATURE_MODULES, PRO_FEATURES, TAGLINE } from "@/lib/marketingCopy";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.06 } }),
};

export default function Features() {
  const { authed, enter } = useMarketingAuth();
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => { window.scrollTo(0, 0); }, []);

  const modulesByTitle = Object.fromEntries(FEATURE_MODULES.map((m) => [m.title, m]));

  return (
    <div className="min-h-screen bg-helm-ink text-helm-cream overflow-x-hidden">
      <MarketingNav authed={authed} onEnter={enter} active="/features" />

      <section className="px-6 pt-36 md:pt-48 pb-16">
        <div className="mx-auto max-w-3xl">
          <motion.p variants={fade} initial="hidden" animate="show" custom={0}
            className="font-mono text-xs uppercase tracking-[0.3em] text-helm-slate">{CATEGORY}</motion.p>
          <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
            className="font-display mt-8 text-5xl md:text-6xl font-medium tracking-[-0.03em] leading-[1.05]">
            Everything in the cockpit
          </motion.h1>
          <motion.p variants={fade} initial="hidden" animate="show" custom={2}
            className="mt-6 text-lg text-helm-slate leading-relaxed">
            Briefing, decisions, departments, and the rest of the cockpit,
            each designed to answer a specific leadership question:
            what changed, what to decide, what to delegate, and whether it landed.
          </motion.p>
        </div>
      </section>

      <section className="px-6 pb-20">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="h-px w-10 bg-helm-gold mb-6" aria-hidden />
            <h2 className="font-display text-3xl md:text-4xl font-medium tracking-tight max-w-xl leading-tight">
              Production, Procurement, and Decision Center as they appear in Helm.
            </h2>
          </motion.div>
          <div className="mt-12">
            <ProductScreens />
          </div>
        </div>
      </section>

      <section className="px-6 pb-16 border-t border-helm-cream/[0.05] pt-16">
        <div className="mx-auto max-w-3xl">
          <div className="h-px w-10 bg-helm-gold mb-6" aria-hidden />
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-helm-slate mb-6">Included in Helm</p>
          <ul className="space-y-3">
            {PRO_FEATURES.map((f) => (
              <li key={f} className="text-sm text-helm-cream/85 border-b border-helm-cream/[0.06] pb-3">
                {f}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {FEATURE_CATEGORIES.map((cat) => (
        <section key={cat.id} className="px-6 py-16 border-t border-helm-cream/[0.05]">
          <div className="mx-auto max-w-3xl">
            <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }} className="mb-10">
              <h2 className="font-display text-3xl font-medium tracking-tight text-helm-cream">{cat.label}</h2>
              <p className="mt-3 text-helm-slate text-sm leading-relaxed">{cat.intro}</p>
            </motion.div>
            <div className="space-y-0 border-t border-helm-cream/[0.06]">
              {cat.modules.map((title, i) => {
                const mod = modulesByTitle[title];
                if (!mod) return null;
                return (
                  <motion.article key={mod.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }}
                    className="py-8 border-b border-helm-cream/[0.06]">
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-helm-slate">{mod.ceoValue}</p>
                    <h3 className="font-display mt-2 text-2xl tracking-tight text-helm-cream">{mod.title}</h3>
                    <p className="mt-3 text-sm text-helm-slate leading-relaxed">{mod.body}</p>
                    <p className="mt-4 text-sm text-helm-slate/90 leading-relaxed pl-4 border-l border-helm-cream/15">{mod.example}</p>
                  </motion.article>
                );
              })}
            </div>
          </div>
        </section>
      ))}

      <DepartmentsShowcase compact />

      <section className="px-6 py-24 border-t border-helm-cream/[0.05]">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto h-px w-10 bg-helm-gold mb-8" aria-hidden />
          <p className="font-display text-3xl md:text-4xl font-medium tracking-tight text-helm-cream leading-tight">{TAGLINE}</p>
          <p className="mt-4 text-sm text-helm-slate">One plan. Full cockpit. Live in minutes.</p>
          <button type="button" onClick={enter}
            className="mt-10 group inline-flex items-center gap-2 rounded-md bg-helm-cream text-helm-navy font-medium px-6 py-3 hover:bg-helm-gold transition-colors">
            {authed ? "Open your cockpit" : "Get started with Helm"}
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </button>
          <p className="mt-6 text-sm text-helm-slate flex flex-wrap items-center justify-center gap-x-5 gap-y-1">
            <a
              href="/#pricing"
              className="hover:text-helm-cream transition-colors"
              onClick={(e) => {
                e.preventDefault();
                goToHomeHash(navigate, location, "pricing");
              }}
            >
              View pricing
            </a>
            <Link to="/about" className="hover:text-helm-cream transition-colors">About Helm</Link>
            <Link to="/security" className="hover:text-helm-cream transition-colors">Security</Link>
          </p>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
