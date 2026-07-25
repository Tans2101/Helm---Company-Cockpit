import { useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Sparkles, Send, UserCheck, TrendingUp, TrendingDown, Minus, Lock } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { GlassCard, SectionLabel, LoadingScreen, ProBadge, Delta } from "@/components/kit";
import { cn } from "@/lib/utils";

const toneDot = { positive: "bg-emerald-400", negative: "bg-rose-400", neutral: "bg-zinc-500" };

export default function Briefing() {
  const { data, loading, setData } = useFetch("/briefing");
  const { data: company } = useFetch("/company");
  const [genLoading, setGenLoading] = useState(false);
  const navigate = useNavigate();

  if (loading || !data) return <LoadingScreen label="Assembling briefing" />;

  const generate = async () => {
    setGenLoading(true);
    try {
      const { data: res } = await api.post("/briefing/generate");
      setData({ ...data, ai_summary: res.ai_summary });
      toast.success("Briefing synthesized");
    } catch (e) {
      toast.error("Upgrade to Pro to generate AI briefings");
      navigate("/billing");
    } finally {
      setGenLoading(false);
    }
  };

  const greeting = `${data.greeting}, ${company?.ceo_name?.split(" ")[0] || "CEO"}`;

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8 fade-up">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">{data.date} · Morning Briefing</p>
          <h1 className="text-3xl md:text-5xl font-light tracking-tight text-white">{greeting}.</h1>
          <p className="text-zinc-400 mt-3 max-w-2xl text-base md:text-lg leading-relaxed">{data.headline}</p>
        </div>
      </div>

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
              <SectionLabel>Kalun's synthesis</SectionLabel>
              {!data.is_pro && <ProBadge />}
            </div>
            {data.ai_summary ? (
              <p className="text-zinc-200 leading-relaxed text-[15px]">{data.ai_summary}</p>
            ) : data.is_pro ? (
              <div>
                <p className="text-zinc-500 text-sm mb-4">Generate an AI synthesis of today's signal from your live company data.</p>
                <button data-testid="generate-briefing-btn" onClick={generate} disabled={genLoading}
                  className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2 transition-colors hover:bg-gold-hover disabled:opacity-60">
                  {genLoading ? "Synthesizing…" : "Generate briefing"}
                  {!genLoading && <Send className="w-3.5 h-3.5" />}
                </button>
              </div>
            ) : (
              <div>
                <p className="text-zinc-400 text-sm leading-relaxed mb-4">
                  Your morning executive briefing — synthesized from finance, sales, and team signal into three sentences that matter. Available on Pro.
                </p>
                <button data-testid="briefing-upgrade-btn" onClick={() => navigate("/billing")}
                  className="inline-flex items-center gap-2 rounded-md border border-gold/40 text-gold text-sm font-medium px-4 py-2 transition-colors hover:bg-gold/10">
                  <Lock className="w-3.5 h-3.5" /> Unlock with Pro
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
              <button key={d.id} onClick={() => navigate("/decisions")} data-testid={`decide-${d.id}`}
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
    </div>
  );
}
