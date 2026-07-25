import { useFetch } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const trustColor = (s) => (s >= 90 ? "text-emerald-400" : s >= 80 ? "text-gold" : "text-amber-400");

export default function People() {
  const { data, loading } = useFetch("/people");
  if (loading || !data) return <LoadingScreen label="Loading roster" />;

  return (
    <div>
      <PageHeader title="People" subtitle="Roster, trust scores and quality — a drill-down into who delivers, consistently." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Avg Trust Score</p>
          <p className={cn("font-mono text-3xl mt-2", trustColor(data.avg_trust))}>{data.avg_trust}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">People</p>
          <p className="font-mono text-3xl text-white mt-2">{data.people.length}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Tasks Shipped</p>
          <p className="font-mono text-3xl text-white mt-2">{data.people.reduce((a, p) => a + p.tasks_done, 0)}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Departments</p>
          <p className="font-mono text-3xl text-white mt-2">{new Set(data.people.map((p) => p.department)).size}</p>
        </GlassCard>
      </div>

      <SectionLabel className="mb-4">Roster</SectionLabel>
      <div className="grid md:grid-cols-2 gap-3">
        {data.people.map((p) => (
          <GlassCard key={p.id} className="p-4 fade-up transition-transform hover:-translate-y-0.5" data-testid={`person-${p.id}`}>
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center text-gold shrink-0">{p.name.split(" ").map((n) => n[0]).join("")}</div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm">{p.name}</p>
                <p className="text-xs text-zinc-500">{p.role} · {p.department}</p>
              </div>
              <div className="text-right">
                <p className={cn("font-mono text-xl", trustColor(p.trust_score))}>{p.trust_score}</p>
                <p className="text-[10px] text-zinc-600 uppercase tracking-wide">trust</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-white/5 text-center">
              <div><p className="font-mono text-white text-sm">{p.quality}</p><p className="text-[10px] text-zinc-600">quality</p></div>
              <div><p className="font-mono text-white text-sm">{p.tasks_done}</p><p className="text-[10px] text-zinc-600">shipped</p></div>
              <div><p className="font-mono text-white text-sm">{p.tenure}</p><p className="text-[10px] text-zinc-600">tenure</p></div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
