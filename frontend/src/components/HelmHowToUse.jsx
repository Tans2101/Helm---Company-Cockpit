import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Sun, Zap, Calendar, Check, ChevronRight, LayoutDashboard,
  GitBranch, MessageSquareText, DollarSign, Briefcase, Plug,
  BookOpen, Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  HOW_TO_USE_INTRO,
  HOW_TO_USE_RHYTHMS,
  HOW_TO_USE_MODULES,
  HOW_TO_USE_CHECKLIST,
  TAGLINE,
} from "@/lib/marketingCopy";

const RHYTHM_ICONS = { sun: Sun, zap: Zap, calendar: Calendar };

const MODULE_ICONS = {
  Briefing: LayoutDashboard,
  Decisions: GitBranch,
  "Ask Helm": MessageSquareText,
  Financials: DollarSign,
  Pipeline: Briefcase,
  Departments: Building2,
  Integrations: Plug,
};

export default function HelmHowToUse({ className }) {
  const [activeRhythm, setActiveRhythm] = useState(HOW_TO_USE_RHYTHMS[0].id);
  const rhythm = HOW_TO_USE_RHYTHMS.find((r) => r.id === activeRhythm) || HOW_TO_USE_RHYTHMS[0];
  const RhythmIcon = RHYTHM_ICONS[rhythm.icon] || Sun;

  return (
    <div className={cn("w-full max-w-3xl mx-auto text-left", className)}>
      <div className="flex items-start gap-4 mb-8">
        <div className="w-12 h-12 rounded-xl bg-helm-gold/12 border border-helm-gold/35 flex items-center justify-center shrink-0">
          <BookOpen className="w-6 h-6 text-helm-gold" />
        </div>
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-helm-gold">Getting started</p>
          <h2 className="mt-1 text-2xl md:text-3xl font-light tracking-tight text-helm-fg">
            {HOW_TO_USE_INTRO.title}
          </h2>
          <p className="mt-2 text-sm text-helm-muted leading-relaxed max-w-xl">
            {HOW_TO_USE_INTRO.subtitle}
          </p>
        </div>
      </div>

      <p className="text-sm text-helm-muted leading-relaxed border-l-2 border-helm-gold/35 pl-4 mb-10">
        {HOW_TO_USE_INTRO.lead}
        <span className="block mt-2 text-helm-muted italic">{TAGLINE}</span>
      </p>

      {/* Rhythm tabs */}
      <div className="flex flex-wrap gap-2 mb-6">
        {HOW_TO_USE_RHYTHMS.map((r) => {
          const Icon = RHYTHM_ICONS[r.icon] || Sun;
          const on = r.id === activeRhythm;
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => setActiveRhythm(r.id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-medium transition-colors",
                on
                  ? "bg-helm-gold/12 text-helm-gold border border-helm-gold/35"
                  : "bg-helm-fg/[0.03] text-helm-muted border border-helm-line hover:text-helm-fg hover:border-helm-line",
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {r.label}
              <span className="text-[10px] font-mono opacity-70">{r.time}</span>
            </button>
          );
        })}
      </div>

      {/* Active rhythm steps */}
      <div className="rounded-xl border border-helm-line bg-helm-card overflow-hidden mb-10">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-helm-line bg-helm-fg/[0.02]">
          <RhythmIcon className="w-5 h-5 text-helm-gold" />
          <div>
            <p className="text-sm font-medium text-helm-fg">{rhythm.label}</p>
            <p className="text-[10px] font-mono uppercase tracking-wider text-helm-muted">{rhythm.time}</p>
          </div>
        </div>
        <ol className="divide-y divide-helm-fg/[0.04]">
          {rhythm.steps.map((step, i) => (
            <li key={step.title} className="flex gap-4 px-5 py-4 hover:bg-helm-fg/[0.02] transition-colors">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-helm-gold/12 text-[11px] font-mono text-helm-gold border border-helm-gold/35">
                {i + 1}
              </span>
              <div className="min-w-0 pt-0.5">
                <p className="text-sm font-medium text-helm-fg">{step.title}</p>
                <p className="mt-1 text-xs text-helm-muted leading-relaxed">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {/* Module quick reference */}
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-helm-muted mb-4">Where to find things</p>
      <div className="grid sm:grid-cols-2 gap-3 mb-10">
        {HOW_TO_USE_MODULES.map((m) => {
          const Icon = MODULE_ICONS[m.nav] || LayoutDashboard;
          return (
            <div
              key={m.nav}
              className="group flex items-start gap-3 rounded-lg border border-helm-line bg-helm-fg/[0.02] px-4 py-3 hover:border-helm-gold/35 hover:bg-helm-gold/10 transition-colors"
            >
              <Icon className="w-4 h-4 text-helm-muted group-hover:text-helm-gold shrink-0 mt-0.5 transition-colors" />
              <div className="min-w-0">
                <p className="text-xs font-medium text-helm-fg flex items-center gap-1">
                  {m.nav}
                  <ChevronRight className="w-3 h-3 text-helm-muted opacity-0 group-hover:opacity-100 transition-opacity" />
                </p>
                <p className="text-[11px] text-helm-muted mt-0.5 leading-relaxed">{m.tip}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* First-week checklist */}
      <div className="rounded-xl border border-helm-line border-l-2 border-l-helm-gold/70 bg-helm-card p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-helm-gold mb-4">Your first week</p>
        <ul className="space-y-2.5">
          {HOW_TO_USE_CHECKLIST.map((item) => (
            <li key={item} className="flex items-start gap-2.5 text-sm text-helm-muted">
              <Check className="w-4 h-4 text-helm-gold shrink-0 mt-0.5" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-helm-muted">
          Need more detail?{" "}
          <Link to="/features" className="text-helm-muted hover:text-helm-fg underline underline-offset-2 transition-colors">
            See all features
          </Link>
        </p>
      </div>
    </div>
  );
}
