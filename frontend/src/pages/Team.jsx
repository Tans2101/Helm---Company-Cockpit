import { AlertTriangle } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

export default function Team() {
  const { data, loading, error, reload } = useFetch("/team");
  if (loading) return <LoadingScreen label="Loading workload" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load team workload"
        message={fetchErrorMessage(error, "Team data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  if (data.members.length === 0) {
    return (
      <div>
        <PageHeader
          title="Team Workload"
          subtitle="Open work and blockers across the team — no guessing, just what's actually outstanding."
        />
        <EmptyState title="No team members yet" body="Invite teammates to see open tasks, overdue work, and blockers." />
      </div>
    );
  }

  const sorted = data.members.slice().sort((a, b) => {
    const overdueDiff = (b.overdue_tasks || 0) - (a.overdue_tasks || 0);
    if (overdueDiff !== 0) return overdueDiff;
    return (b.open_tasks || 0) - (a.open_tasks || 0);
  });

  return (
    <div>
      <PageHeader
        title="Team Workload"
        subtitle="Open work and blockers across the team — no guessing, just what's actually outstanding."
      />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Headcount</p>
          <p className="font-mono text-3xl text-white mt-2">{data.headcount ?? data.members.length}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Total Open Tasks</p>
          <p className="font-mono text-3xl text-white mt-2">{data.total_open_tasks ?? 0}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up border-rose-400/20">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Total Overdue</p>
          <div className="flex items-center gap-2 mt-2">
            {(data.total_overdue || 0) > 0 ? <AlertTriangle className="w-5 h-5 text-rose-400" /> : null}
            <p className={cn("font-mono text-3xl", (data.total_overdue || 0) > 0 ? "text-rose-400" : "text-white")}>
              {data.total_overdue ?? 0}
            </p>
          </div>
        </GlassCard>
      </div>

      <SectionLabel className="mb-4">Workload by person</SectionLabel>
      <div className="space-y-2.5">
        {sorted.map((m) => (
          <GlassCard key={m.name} className="p-4 fade-up" data-testid={`member-${m.name}`}>
            <div className="flex items-center gap-4">
              <div className="w-9 h-9 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center text-sm text-gold shrink-0">
                {m.name[0]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white flex items-center gap-1.5 flex-wrap">
                  {m.name}
                  {m.blocked ? (
                    <span className="text-[9px] font-mono uppercase text-amber-400 bg-amber-400/10 rounded px-1 py-0.5">blocked</span>
                  ) : m.posted_today ? (
                    <span className="text-[9px] font-mono uppercase text-emerald-400 bg-emerald-400/10 rounded px-1 py-0.5">updated</span>
                  ) : null}
                </p>
                <p className="text-xs text-zinc-500">{m.role}</p>
              </div>
              <div className="flex items-center gap-5 shrink-0 text-right">
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Open</p>
                  <p className="font-mono text-white text-sm">{m.open_tasks}</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Overdue</p>
                  <p className={cn("font-mono text-sm", (m.overdue_tasks || 0) > 0 ? "text-amber-400" : "text-white")}>
                    {m.overdue_tasks ?? 0}
                  </p>
                </div>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
