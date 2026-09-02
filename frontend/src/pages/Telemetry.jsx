import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ZAxis,
} from "recharts";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, Delta, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const GOLD = "#c9a962";

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-white/10 bg-[#141417] px-3 py-2 text-xs">
      {label && <p className="text-zinc-400 mb-1 font-mono">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="text-white font-mono">
          <span style={{ color: p.color }}>●</span> {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
}

function Sparkline({ data }) {
  const chart = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={chart}>
        <Line type="monotone" dataKey="v" stroke={GOLD} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const riskColor = (score) => (score >= 15 ? "#ef4444" : score >= 8 ? "#f59e0b" : "#10b981");

export default function Telemetry() {
  const { data, loading, error, reload } = useFetch("/telemetry");
  if (loading) return <LoadingScreen label="Loading telemetry" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load telemetry"
        message={fetchErrorMessage(error, "Telemetry data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  if ((data.kpis || []).length === 0) return <div><PageHeader title="Telemetry" subtitle="Live KPIs and growth trends from your real data." /><EmptyState title="No telemetry yet" body="Log financials and add your team — your KPIs build from real data." /></div>;

  const asOf = data.data_as_of ? new Date(data.data_as_of).toLocaleString() : null;

  return (
    <div>
      <PageHeader title="Telemetry" subtitle="Live KPIs from your integrated sources — financials, pipeline, people, and tasks. Refreshes on every load." />

      {data.sources?.length > 0 && (
        <GlassCard className="p-4 mb-6 fade-up" data-testid="telemetry-sources">
          <SectionLabel className="mb-2">Data sources</SectionLabel>
          {asOf && <p className="text-[11px] font-mono text-zinc-600 mb-3">As of {asOf}</p>}
          <div className="flex flex-wrap gap-2">
            {data.sources.map((s) => (
              <span key={s.label} className="inline-flex flex-col rounded-md border border-white/10 bg-white/[0.02] px-3 py-2 text-left">
                <span className="text-xs text-white">{s.label}</span>
                <span className="text-[10px] text-zinc-500">{s.detail}</span>
                <span className={cn("text-[9px] font-mono uppercase mt-1", s.freshness === "live" ? "text-emerald-400" : s.freshness === "hourly" ? "text-sky-400" : "text-amber-400")}>{s.freshness}</span>
              </span>
            ))}
          </div>
        </GlassCard>
      )}

      {/* KPI grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {data.kpis.map((k, i) => (
          <GlassCard key={k.label} className="p-4 fade-up" style={{ animationDelay: `${i * 50}ms` }} data-testid={`kpi-${i}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">{k.label}</span>
              <Delta value={k.delta} tone={k.tone} />
            </div>
            <span className="font-mono text-3xl text-white">{k.value}</span>
            <div className="mt-2 -mx-1"><Sparkline data={k.spark} /></div>
          </GlassCard>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mb-6">
        {/* Revenue trend */}
        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">MRR vs Target</SectionLabel>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={data.revenue_trend} margin={{ left: -18, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="mrr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={GOLD} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="month" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="target" name="Target" stroke="#52525b" strokeDasharray="4 4" fill="none" strokeWidth={1.5} />
              <Area type="monotone" dataKey="mrr" name="MRR" stroke={GOLD} strokeWidth={2} fill="url(#mrr)" />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        {/* Funnel */}
        {data.funnel.length > 0 && (
        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">Sales Funnel</SectionLabel>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.funnel} layout="vertical" margin={{ left: 20, right: 16 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" horizontal={false} />
              <XAxis type="number" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="stage" stroke="#a1a1aa" fontSize={11} tickLine={false} axisLine={false} width={72} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="value" name="Count" radius={[0, 4, 4, 0]}>
                {data.funnel.map((_, i) => <Cell key={i} fill={GOLD} fillOpacity={1 - i * 0.14} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
        )}
      </div>
    </div>
  );
}
