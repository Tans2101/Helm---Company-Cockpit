import { useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, PenLine } from "lucide-react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
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

const emptyRisk = () => ({ id: "", name: "", likelihood: 3, impact: 3, category: "General" });

export default function Telemetry() {
  const { data, loading, error, reload } = useFetch("/telemetry");
  const [editing, setEditing] = useState(false);
  const [risks, setRisks] = useState([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

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
  const canWrite = data.can_write;

  const openEdit = () => {
    setRisks((data.risks || []).length ? data.risks.map((r) => ({ ...r })) : [{ ...emptyRisk() }]);
    setNotes(data.notes || "");
    setEditing(true);
  };

  const saveRisks = async () => {
    setBusy(true);
    try {
      await api.patch("/telemetry", {
        risks: risks.filter((r) => r.name?.trim()),
        notes: notes.trim(),
      });
      toast.success("Telemetry updated");
      setEditing(false);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Telemetry"
        subtitle="Live KPIs from your integrated sources — financials, pipeline, people, and tasks."
        action={canWrite ? (
          <button type="button" onClick={openEdit} className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm px-3 py-2 hover:bg-gold/15">
            <PenLine className="w-3.5 h-3.5" /> Edit risks
          </button>
        ) : null}
      />

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

      {(data.risks?.length > 0 || data.notes || canWrite) && (
        <GlassCard className="p-5 fade-up" data-testid="telemetry-risks">
          <SectionLabel className="mb-4">Risk radar</SectionLabel>
          {data.notes && !editing && (
            <p className="text-sm text-zinc-400 mb-4 leading-relaxed border-l-2 border-gold/30 pl-3">{data.notes}</p>
          )}
          {!editing && data.risks?.length > 0 && (
            <div className="grid sm:grid-cols-2 gap-3">
              {data.risks.map((r) => {
                const score = (r.likelihood || 1) * (r.impact || 1);
                return (
                  <div key={r.id || r.name} className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-white">{r.name}</p>
                      <span className="text-[10px] font-mono rounded px-1.5 py-0.5" style={{ color: riskColor(score), background: `${riskColor(score)}15` }}>{score}</span>
                    </div>
                    <p className="text-[10px] text-zinc-600 mt-1 font-mono uppercase">{r.category}</p>
                  </div>
                );
              })}
            </div>
          )}
          {!editing && !data.risks?.length && canWrite && (
            <p className="text-sm text-zinc-600">No risks logged yet — click Edit risks to add what you&apos;re watching.</p>
          )}
        </GlassCard>
      )}

      {editing && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setEditing(false)} />
          <GlassCard className="relative w-full sm:max-w-lg m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6 max-h-[90vh] overflow-y-auto" data-testid="telemetry-edit-form">
            <h3 className="text-lg text-white font-light mb-4">Edit telemetry risks</h3>
            <label className="text-xs text-zinc-500 block mb-4">Notes
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Context for your risk radar…"
                className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 resize-none focus:outline-none focus:border-gold/40" />
            </label>
            <div className="space-y-3">
              {risks.map((r, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-start">
                  <input value={r.name} onChange={(e) => setRisks((prev) => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                    placeholder="Risk name" className="col-span-6 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-2 py-1.5 focus:outline-none focus:border-gold/40" />
                  <input value={r.category} onChange={(e) => setRisks((prev) => prev.map((x, j) => j === i ? { ...x, category: e.target.value } : x))}
                    placeholder="Category" className="col-span-3 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-2 py-1.5 focus:outline-none focus:border-gold/40" />
                  <button type="button" onClick={() => setRisks((prev) => prev.filter((_, j) => j !== i))} className="col-span-1 text-zinc-600 hover:text-rose-400 p-1"><Trash2 className="w-4 h-4" /></button>
                  <div className="col-span-6 flex gap-2">
                    <label className="text-[10px] text-zinc-600 flex-1">Likelihood
                      <input type="number" min={1} max={5} value={r.likelihood} onChange={(e) => setRisks((prev) => prev.map((x, j) => j === i ? { ...x, likelihood: parseInt(e.target.value, 10) || 1 } : x))}
                        className="mt-0.5 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-2 py-1 focus:outline-none focus:border-gold/40" />
                    </label>
                    <label className="text-[10px] text-zinc-600 flex-1">Impact
                      <input type="number" min={1} max={5} value={r.impact} onChange={(e) => setRisks((prev) => prev.map((x, j) => j === i ? { ...x, impact: parseInt(e.target.value, 10) || 1 } : x))}
                        className="mt-0.5 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-2 py-1 focus:outline-none focus:border-gold/40" />
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <button type="button" onClick={() => setRisks((prev) => [...prev, emptyRisk()])}
              className="mt-3 inline-flex items-center gap-1 text-xs text-gold hover:text-gold-hover">
              <Plus className="w-3.5 h-3.5" /> Add risk
            </button>
            <div className="flex gap-2 mt-5">
              <button type="button" onClick={() => setEditing(false)} className="rounded-md border border-white/10 text-zinc-300 text-sm px-4 py-2.5 hover:bg-white/5">Cancel</button>
              <button type="button" onClick={saveRisks} disabled={busy} className="flex-1 rounded-md bg-gold text-black font-medium text-sm py-2.5 hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : "Save"}</button>
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
