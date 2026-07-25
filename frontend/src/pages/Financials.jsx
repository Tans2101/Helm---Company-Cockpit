import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useFetch } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen } from "@/components/kit";

const GOLD = "#c9a962";
const PIE = ["#c9a962", "#8b7a4a", "#6b6b74", "#3f3f46", "#27272a"];

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-white/10 bg-[#141417] px-3 py-2 text-xs">
      {label && <p className="text-zinc-400 mb-1 font-mono">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="text-white font-mono"><span style={{ color: p.color }}>●</span> {p.name}: {p.value}</p>
      ))}
    </div>
  );
}

export default function Financials() {
  const { data, loading } = useFetch("/financials");
  if (loading || !data) return <LoadingScreen label="Loading financials" />;

  const headline = [
    { label: "MRR", value: data.mrr },
    { label: "ARR", value: data.arr },
    { label: "Runway", value: `${data.runway_months}mo` },
    { label: "Monthly Burn", value: data.burn },
    { label: "Cash", value: data.cash },
    { label: "Gross Margin", value: data.gross_margin },
  ];

  return (
    <div>
      <PageHeader title="Financials" subtitle="Revenue, runway, burn and scenario planning — the numbers that decide how long you have to win." />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {headline.map((h, i) => (
          <GlassCard key={h.label} className="p-4 fade-up" style={{ animationDelay: `${i*40}ms` }} data-testid={`fin-${h.label}`}>
            <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">{h.label}</p>
            <p className="font-mono text-2xl text-white mt-2">{h.value}</p>
          </GlassCard>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        <GlassCard className="p-5 lg:col-span-2 fade-up">
          <SectionLabel className="mb-4">Revenue vs Expenses ($K)</SectionLabel>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data.revenue_series} margin={{ left: -18, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={GOLD} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="month" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="revenue" name="Revenue" stroke={GOLD} strokeWidth={2} fill="url(#rev)" />
              <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#71717a" strokeWidth={1.5} fill="none" strokeDasharray="4 4" />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">Expense Breakdown</SectionLabel>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={data.expense_breakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={48} outerRadius={80} paddingAngle={2} stroke="none">
                {data.expense_breakdown.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {data.expense_breakdown.map((e, i) => (
              <div key={e.name} className="flex items-center gap-2 text-xs">
                <span className="w-2 h-2 rounded-sm" style={{ background: PIE[i % PIE.length] }} />
                <span className="text-zinc-400 flex-1">{e.name}</span>
                <span className="font-mono text-zinc-300">{e.value}%</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <GlassCard className="p-5 lg:col-span-2 fade-up">
          <SectionLabel className="mb-4">Monthly Burn ($K)</SectionLabel>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.burn_series} margin={{ left: -18, right: 8 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="month" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="burn" name="Burn" fill={GOLD} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">Runway Scenarios</SectionLabel>
          <div className="space-y-3">
            {data.scenarios.map((s) => (
              <div key={s.name} className="rounded-lg border border-white/5 bg-white/[0.02] p-3" data-testid={`scenario-${s.name}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white">{s.name}</span>
                  <span className="font-mono text-gold text-sm">{s.runway}mo</span>
                </div>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{s.desc}</p>
                <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full bg-gold/70 rounded-full" style={{ width: `${Math.min(s.runway/24*100,100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
