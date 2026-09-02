import { useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Sparkles, Send, UserCheck, TrendingUp, TrendingDown, Minus, Users, CheckCircle2, Circle } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { GlassCard, SectionLabel, LoadingScreen, ErrorScreen, Delta } from "@/components/kit";
import { cn } from "@/lib/utils";
import Onboarding from "@/pages/Onboarding";
import { timeGreeting } from "@/lib/greeting";

const toneDot = { positive: "bg-emerald-400", negative: "bg-rose-400", neutral: "bg-zinc-500" };

export default function Briefing() {
  const { data, loading: briefingLoading, error: briefingError, reload: reloadBriefing, setData } = useFetch("/briefing");
  const { data: company, loading: companyLoading, error: companyError, reload: reloadCompany } = useFetch("/company");
  const { data: checklist } = useFetch("/onboarding/checklist");
  const [genLoading, setGenLoading] = useState(false);
  const navigate = useNavigate();

  const loading = briefingLoading || companyLoading;
  const error = briefingError || companyError;
  const reload = () => { reloadBriefing(); reloadCompany(); };

  if (loading) return <LoadingScreen label="Assembling briefing" />;
  if (error || !data || !company) {
    return (
      <ErrorScreen
        label="Could not load briefing"
        message={fetchErrorMessage(error, "Briefing data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  if (company.onboarding_done === false) return <Onboarding />;

  const generate = async () => {
    setGenLoading(true);
    try {
      const { data: res } = await api.post("/briefing/generate");
      setData({ ...data, ai_summary: res.ai_summary });
      toast.success("Briefing synthesized");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate briefing");
    } finally {
      setGenLoading(false);
    }
  };

  const { greeting: timeGreet, briefingLabel } = timeGreeting();
  const greeting = `${timeGreet}, ${company?.ceo_name?.split(" ")[0] || "CEO"}`;

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8 fade-up">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">{data.date} · {briefingLabel}</p>
          <h1 className="text-3xl md:text-5xl font-light tracking-tight text-white">{greeting}.</h1>
          <p className="text-zinc-400 mt-3 max-w-2xl text-base md:text-lg leading-relaxed">{data.headline}</p>
        </div>
      </div>

      {checklist && !checklist.complete && (
        <GlassCard glow className="p-5 mb-6 fade-up border-gold/20" data-testid="onboarding-checklist">
          <div className="flex items-center gap-1.5 mb-3">
            <Sparkles className="w-4 h-4 text-gold" />
            <SectionLabel>Finish setting up Helm</SectionLabel>
            <span className="ml-auto font-mono text-xs text-zinc-500">{checklist.steps.filter((s) => s.done).length}/{checklist.steps.length}</span>
          </div>
          <div className="grid sm:grid-cols-2 gap-2">
            {checklist.steps.map((s) => (
              <button key={s.id} data-testid={`setup-${s.id}`} onClick={() => navigate(s.route)}
                className={cn("flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors",
                  s.done ? "border-emerald-400/20 bg-emerald-400/[0.04]" : "border-white/10 bg-white/[0.02] hover:border-gold/30")}>
                {s.done ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" /> : <Circle className="w-4 h-4 text-zinc-600 shrink-0" />}
                <span className={cn("text-sm", s.done ? "text-zinc-500 line-through" : "text-zinc-200")}>{s.label}</span>
                {!s.done && <ArrowUpRight className="w-3.5 h-3.5 text-gold ml-auto shrink-0" />}
              </button>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Top metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6">
        {data.metrics.map((m, i) => (
          <GlassCard key={m.label} className="p-4 fade-up" style={{ animationDelay: `${i * 60}ms` }} data-testid={`briefing-metric-${i}`}>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">{m.label}</span>
              <span className={cn("w-1.5 h-1.5 rounded-full", toneDot[m.tone])} />
            </div>
            <div className="mt-3 flex items-end justify-between">
              <span className="font-mono text-2xl md:text-3xl text-white">{m.value}</span>
              <Delta value={m.delta} tone={m.tone} />
            </div>
          </GlassCard>
        ))}
      </div>

      {/* AI synthesis */}
      <GlassCard glow className="p-5 md:p-6 mb-6 fade-up border-gold/20">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-gold" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <SectionLabel>Helm's synthesis</SectionLabel>
            </div>
            {data.ai_summary ? (
              <p className="text-zinc-200 leading-relaxed text-[15px]">{data.ai_summary}</p>
            ) : (
              <div>
                <p className="text-zinc-500 text-sm mb-4">Generate an AI synthesis of today's signal from your live company data.</p>
                <button data-testid="generate-briefing-btn" onClick={generate} disabled={genLoading}
                  className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2 transition-colors hover:bg-gold-hover disabled:opacity-60">
                  {genLoading ? "Synthesizing…" : "Generate briefing"}
                  {!genLoading && <Send className="w-3.5 h-3.5" />}
                </button>
              </div>
            )}
          </div>
        </div>
      </GlassCard>

      {/* Three columns */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* What changed */}
        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">What changed</SectionLabel>
          <div className="space-y-4">
            {data.what_changed.map((c, i) => (
              <div key={i} className="flex gap-3" data-testid={`changed-${i}`}>
                <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", toneDot[c.tone])} />
                <div>
                  <p className="text-sm text-white leading-snug">{c.title}</p>
                  <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{c.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* What to decide */}
        <GlassCard className="p-5 fade-up">
          <div className="flex items-center justify-between mb-4">
            <SectionLabel>What to decide</SectionLabel>
            <span className="font-mono text-xs text-gold">{data.what_to_decide.length}</span>
          </div>
          <div className="space-y-3">
            {data.what_to_decide.map((d) => (
              <button key={d.id} onClick={() => navigate("/app/decisions")} data-testid={`decide-${d.id}`}
                className="w-full text-left rounded-lg border border-white/5 bg-white/[0.02] p-3 transition-colors hover:border-gold/30 hover:bg-white/[0.04] group">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-white leading-snug">{d.title}</p>
                  <ArrowUpRight className="w-4 h-4 text-zinc-600 group-hover:text-gold shrink-0" />
                </div>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{d.detail}</p>
                <span className={cn("inline-block mt-2 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded",
                  d.urgency === "high" ? "text-rose-400 bg-rose-400/10" : "text-amber-400 bg-amber-400/10")}>
                  {d.urgency} priority
                </span>
              </button>
            ))}
          </div>
        </GlassCard>

        {/* What to delegate */}
        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">What to delegate</SectionLabel>
          <div className="space-y-3">
            {data.what_to_delegate.map((d, i) => (
              <div key={i} className="rounded-lg border border-white/5 bg-white/[0.02] p-3" data-testid={`delegate-${i}`}>
                <p className="text-sm text-white leading-snug">{d.title}</p>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{d.detail}</p>
                <div className="flex items-center gap-1.5 mt-2 text-gold">
                  <UserCheck className="w-3.5 h-3.5" />
                  <span className="text-xs">{d.owner}</span>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {data.team_updates && data.team_updates.length > 0 && (
        <GlassCard className="p-5 mt-4 fade-up" data-testid="briefing-team-updates">
          <div className="flex items-center gap-1.5 mb-4">
            <Users className="w-4 h-4 text-gold" />
            <SectionLabel>Today's team updates</SectionLabel>
            <span className="font-mono text-xs text-gold ml-auto">{data.team_updates.length}</span>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {data.team_updates.map((u, i) => (
              <div key={i} className="rounded-lg border border-white/5 bg-white/[0.02] p-3" data-testid={`team-update-${i}`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-white">{u.user_name}</span>
                  {u.blocker && <span className="text-[10px] text-amber-400 bg-amber-400/10 rounded px-1.5 py-0.5 font-mono uppercase tracking-wide">Blocked</span>}
                  <span className="text-[10px] text-zinc-600 ml-auto font-mono">{u.ago}</span>
                </div>
                <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">{u.text}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  );
}
