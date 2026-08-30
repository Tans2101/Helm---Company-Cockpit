import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight, Sparkles, GitBranch, DollarSign, MessageSquareText,
  Layers, Zap, Command, Check, Star,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.08 } }),
};

function Nav({ authed, onEnter }) {
  return (
    <header className="fixed top-0 inset-x-0 z-50">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mt-4 flex items-center justify-between rounded-full border border-white/[0.06] bg-[#0d0d0f]/70 backdrop-blur-xl px-5 py-2.5">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
              <span className="font-mono text-gold text-sm font-medium">H</span>
            </div>
            <span className="text-white font-semibold tracking-tight">Helm</span>
          </div>
          <button data-testid="nav-signin-btn" type="button" onClick={onEnter}
            className="group flex items-center gap-1.5 rounded-full bg-white text-black text-sm font-medium px-4 py-1.5 transition-colors hover:bg-gold">
            {authed ? "Open cockpit" : "Sign in"}
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      </div>
    </header>
  );
}

/* Product preview — a distilled morning briefing, to SHOW the product */
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
        {[["MRR", "$248K", "text-emerald-400"], ["Runway", "17mo", "text-zinc-400"], ["Burn", "$182K", "text-rose-400"]].map(([l, v, c]) => (
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
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const authed = !loading && !!user;

  const enter = () => {
    if (authed) navigate("/app");
    else navigate("/login");
  };

  useEffect(() => { window.scrollTo(0, 0); }, []);

  const problems = [
    { icon: Layers, title: "The answer is scattered", body: "What needs your attention lives across Slack, Jira, Salesforce, the finance sheet and six dashboards. Nobody has the whole picture — least of all you." },
    { icon: Zap, title: "You react instead of lead", body: "By the time a problem reaches you, it's already a fire. Runway, churn and overload creep up silently between board meetings." },
    { icon: Command, title: "Dashboards ≠ decisions", body: "More charts don't help. You need synthesis — the one number that moved, the one call to make, the one thing to hand off." },
  ];

  const steps = [
    { n: "01", title: "Pulls it in", body: "Helm connects to Google, QuickBooks, Paddle and GitHub — your team keeps their tools, you get the signal." },
    { n: "02", title: "Synthesizes", body: "Every morning it distills finance, sales, people and risk into a three-line briefing. Signal over noise." },
    { n: "03", title: "You decide & delegate", body: "Approve, follow up, or hand off in a click — then Helm tracks whether the outcome actually landed." },
  ];

  const features = [
    { icon: Sparkles, title: "Morning Briefing", body: "What changed, what to decide, what to delegate — before your first meeting." },
    { icon: GitBranch, title: "Decision Center", body: "Approvals with AI recommendations and confidence scores, plus outcome checks." },
    { icon: DollarSign, title: "Runway & Burn", body: "Revenue, burn and scenario planning — always know how long you have to win." },
    { icon: MessageSquareText, title: "Ask Helm", body: "Your executive AI chief-of-staff, grounded in your live company data." },
  ];

  const stats = [
    { v: "3 min", l: "to your morning briefing" },
    { v: "8+", l: "tools unified in one view" },
    { v: "118%", l: "avg. NRR of teams on Helm" },
    { v: "40%", l: "fewer status meetings" },
  ];

  const testimonials = [
    { quote: "Helm is the first thing I open. I walk into every morning knowing the one decision that actually matters.", name: "Alex Rivera", role: "Founder & CEO, Northwind Robotics", initials: "AR" },
    { quote: "It replaced my Monday scramble across five dashboards. The briefing just tells me what needs me.", name: "Priya Shah", role: "Co-founder, Ledgerloop", initials: "PS" },
    { quote: "Runway and burn used to live in a spreadsheet I updated monthly. Now it's live — and I sleep better.", name: "Marcus Lin", role: "CEO, Cadence Health", initials: "ML" },
  ];

  return (
    <div className="min-h-screen bg-[#09090b] text-white grain overflow-x-hidden relative">
      <Nav authed={authed} onEnter={enter} />

      {/* Hero */}
      <section className="relative z-10 px-6 pt-36 md:pt-44 pb-20">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[600px]" style={{ background: "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(201,169,98,0.10), transparent 70%)" }} />
        <div className="relative mx-auto max-w-6xl grid lg:grid-cols-[1.1fr_0.9fr] gap-12 lg:gap-8 items-center">
          <div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={0}
              className="font-mono text-xs uppercase tracking-[0.3em] text-gold">CEO Operating System</motion.p>
            <motion.h1 variants={fade} initial="hidden" animate="show" custom={1}
              className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05]">
              Know what matters<br />before your first meeting.
            </motion.h1>
            <motion.p variants={fade} initial="hidden" animate="show" custom={2}
              className="mt-6 text-lg text-zinc-400 leading-relaxed max-w-xl">
              Helm is the command center for founders. It pulls your company's real status in, synthesizes the signal, and tells you the one thing to decide — and who to hand the rest to.
            </motion.p>
            <motion.div variants={fade} initial="hidden" animate="show" custom={3} className="mt-9 flex flex-wrap items-center gap-3 relative z-10">
              <button data-testid="hero-cta-btn" onClick={enter} type="button"
                className="group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-6 py-3 transition-colors hover:bg-gold-hover">
                {authed ? "Open your cockpit" : "Enter Helm"}
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
              <a href="#how" className="inline-flex items-center gap-2 rounded-full border border-white/10 px-6 py-3 text-sm text-zinc-300 transition-colors hover:bg-white/5">
                See how it works
              </a>
            </motion.div>
            <motion.p variants={fade} initial="hidden" animate="show" custom={4} className="mt-6 text-xs text-zinc-600">
              Built for seed & Series A teams of 8–40.
            </motion.p>
          </div>

          <motion.div initial={{ opacity: 0, y: 30, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.9, ease, delay: 0.25 }}>
            <BriefingPreview />
          </motion.div>
        </div>
      </section>

      {/* Trust / stats strip */}
      <section className="relative z-10 px-6 py-12 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <p className="text-center font-mono text-[11px] uppercase tracking-[0.3em] text-zinc-600">
            Illustrative outcomes — not verified customer metrics
          </p>
          <div className="mt-9 grid grid-cols-2 md:grid-cols-4 gap-y-8 gap-x-6">
            {stats.map((s, i) => (
              <motion.div key={s.l} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true }} className="text-center">
                <p className="font-mono text-3xl md:text-4xl text-white">{s.v}</p>
                <p className="mt-2 text-xs text-zinc-500 leading-snug">{s.l}</p>
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
            {problems.map((p, i) => (
              <motion.div key={p.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }}
                className="rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6">
                <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/10 flex items-center justify-center">
                  <p.icon className="w-5 h-5 text-gold" />
                </div>
                <h3 className="mt-5 text-lg text-white tracking-tight">{p.title}</h3>
                <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{p.body}</p>
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
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">Synthesis, not another dashboard.</h2>
          </motion.div>
          <div className="mt-16 grid md:grid-cols-3 gap-8">
            {steps.map((s, i) => (
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
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight max-w-2xl leading-tight">Everything a founder needs — nothing they don't.</h2>
          </motion.div>
          <div className="mt-14 grid sm:grid-cols-2 gap-5">
            {features.map((f, i) => (
              <motion.div key={f.title} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                className="group rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6 transition-colors hover:border-gold/25">
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 rounded-lg bg-gold/10 border border-gold/25 flex items-center justify-center shrink-0">
                    <f.icon className="w-5 h-5 text-gold" />
                  </div>
                  <div>
                    <h3 className="text-lg text-white tracking-tight">{f.title}</h3>
                    <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed">{f.body}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="px-6 py-24 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl">
          <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Illustrative examples</p>
            <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight">What quiet control can feel like.</h2>
            <p className="mt-3 text-sm text-zinc-500 max-w-xl">Composite scenarios for product storytelling — not verified customer testimonials.</p>
          </motion.div>
          <div className="mt-14 grid md:grid-cols-3 gap-5">
            {testimonials.map((t, i) => (
              <motion.div key={t.name} variants={fade} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}
                className="flex flex-col rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6">
                <div className="flex gap-0.5">
                  {[...Array(5)].map((_, s) => <Star key={s} className="w-3.5 h-3.5 text-gold" fill="#c9a962" />)}
                </div>
                <p className="mt-4 text-[15px] text-zinc-200 leading-relaxed flex-1">"{t.quote}"</p>
                <div className="mt-6 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center text-xs text-gold font-mono">{t.initials}</div>
                  <div>
                    <p className="text-sm text-white leading-none">{t.name}</p>
                    <p className="text-xs text-zinc-500 mt-1">{t.role}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative z-10 px-6 py-28 border-t border-white/[0.05]">
        <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true }}
          className="relative mx-auto max-w-3xl text-center rounded-3xl border border-white/[0.08] bg-[#121214]/60 p-12 md:p-16 overflow-hidden">
          <div className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(ellipse 70% 60% at 50% 0%, rgba(201,169,98,0.12), transparent 70%)" }} />
          <h2 className="relative text-3xl md:text-5xl font-light tracking-tight leading-tight">Run your company from<br />one command center.</h2>
          <p className="relative mt-5 text-zinc-400">Quiet control for the person everyone's counting on.</p>
          <div className="relative z-10 mt-9 flex flex-wrap items-center justify-center gap-3">
            <button data-testid="footer-cta-btn" onClick={enter} type="button"
              className="group inline-flex items-center gap-2 rounded-full bg-gold text-black font-medium px-7 py-3 transition-colors hover:bg-gold-hover">
              {authed ? "Open your cockpit" : "Enter Helm"}
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </button>
          </div>
          <div className="relative mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-zinc-600">
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-gold" /> Free to start</span>
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-gold" /> Sign in with Google</span>
            <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3 text-gold" /> Live in minutes</span>
          </div>
        </motion.div>
      </section>

      <footer className="px-6 py-10 border-t border-white/[0.05]">
        <div className="mx-auto max-w-6xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gold/15 border border-gold/30 flex items-center justify-center">
              <span className="font-mono text-gold text-xs">H</span>
            </div>
            <span className="text-sm text-zinc-500">Helm — CEO Operating System</span>
          </div>
          <div className="flex items-center gap-5 text-sm text-zinc-500">
            <Link to="/privacy" className="hover:text-white transition-colors">Privacy</Link>
            <Link to="/terms" className="hover:text-white transition-colors">Terms</Link>
            <Link to="/login" className="hover:text-white transition-colors">Sign in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
