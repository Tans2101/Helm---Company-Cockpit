import { AlertTriangle } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, EmptyState, ErrorScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const statusStyle = {
  overloaded: { label: "Overloaded", color: "text-rose-400", bar: "bg-rose-400" },
  high: { label: "High load", color: "text-amber-400", bar: "bg-amber-400" },
  healthy: { label: "Healthy", color: "text-emerald-400", bar: "bg-emerald-400" },
  available: { label: "Available", color: "text-sky-400", bar: "bg-sky-400" },
};
const fallbackStatus = { label: "Unknown", color: "text-zinc-400", bar: "bg-zinc-500" };

export default function Team() {
  const { data, loading, error, reload } = useFetch("/team");
  if (loading) return <LoadingScreen label="Loading bandwidth" />;
  if (error || !data) return <ErrorScreen onRetry={reload} />;
  if (data.members.length === 0) return <div><PageHeader title="Team Bandwidth" subtitle="Utilization across the team — Helm flags overload early." /><EmptyState title="No team members yet" body="Add your team or connect your tools to see utilization and overload flags." /></div>;

  return (
    <div>
      <PageHeader title="Team Bandwidth" subtitle="Utilization across the team — Helm flags overload before it becomes attrition." />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Avg Utilization</p>
          <p className="font-mono text-3xl text-white mt-2">{data.avg_utilization}%</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up border-rose-400/20">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Overloaded</p>
          <div className="flex items-center gap-2 mt-2">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            <p className="font-mono text-3xl text-white">{data.overloaded_count}</p>
          </div>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Headcount</p>
          <p className="font-mono text-3xl text-white mt-2">{data.members.length}</p>
        </GlassCard>
      </div>

      <SectionLabel className="mb-4">Utilization by person</SectionLabel>
      <div className="space-y-2.5">
        {data.members.slice().sort((a,b) => b.utilization - a.utilization).map((m) => {
          const s = statusStyle[m.status] || fallbackStatus;
          return (
            <GlassCard key={m.name} className="p-4 fade-up" data-testid={`member-${m.name}`}>
              <div className="flex items-center gap-4">
                <div className="w-9 h-9 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center text-sm text-gold shrink-0">{m.name[0]}</div>
                <div className="w-40 shrink-0">
                  <p className="text-sm text-white">{m.name}</p>
                  <p className="text-xs text-zinc-500">{m.role}</p>
                </div>
                <div className="flex-1">
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div className={cn("h-full rounded-full transition-all", s.bar)} style={{ width: `${Math.min(m.utilization, 100)}%` }} />
                  </div>
                </div>
                <div className="w-28 text-right shrink-0">
                  <span className="font-mono text-white">{m.utilization}%</span>
                  <p className={cn("text-[10px] font-mono uppercase tracking-wide", s.color)}>{s.label}</p>
                </div>
              </div>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
