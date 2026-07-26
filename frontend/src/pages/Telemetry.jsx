import { useState } from "react";
import { toast } from "sonner";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ZAxis,
} from "recharts";
import { Plus, Trash2, PenLine, X } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, Delta, EmptyState } from "@/components/kit";

const GOLD = "#c9a962";
const RISK_CATS = ["Ops", "Finance", "People", "Sales", "Compliance", "Market", "Product"];

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
  const chart = (data || []).map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={chart}>
        <Line type="monotone" dataKey="v" stroke={GOLD} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const riskColor = (score) => (score >= 15 ? "#ef4444" : score >= 8 ? "#f59e0b" : "#10b981");

const emptyRisk = () => ({ name: "", likelihood: 3, impact: 3, category: "Ops" });

export default function Telemetry() {
  const { data, loading, reload } = useFetch("/telemetry");
  const [showSales, setShowSales] = useState(false);
  const [showRisk, setShowRisk] = useState(false);
  const [editingRiskId, setEditingRiskId] = useState(null);
  const [pipeline, setPipeline] = useState("");
  const [pipelineDelta, setPipelineDelta] = useState("");
  const [customers, setCustomers] = useState("");
  const [funnelText, setFunnelText] = useState("");
  const [riskForm, setRiskForm] = useState(emptyRisk());
  const [busy, setBusy] = useState(false);

  if (loading || !data) return <LoadingScreen label="Loading telemetry" />;

  const canSales = data.can_write_sales;
  const canOps = data.can_write_ops;
  const kpis = data.kpis || [];
  const funnel = data.funnel || [];
  const risks = data.risks || [];

  if (kpis.length === 0 && funnel.length === 0 && risks.length === 0 && !canSales && !canOps) {
    return (
      <div>
        <PageHeader title="Telemetry" subtitle="Live KPIs, growth trends and the company risk matrix." />
        <EmptyState title="No telemetry yet" body="Log financials and connect your tools — your KPIs and risk matrix build from real data." />
      </div>
    );
  }

  const riskData = risks.map((r) => ({ ...r, x: r.likelihood, y: r.impact, z: r.likelihood * r.impact }));

  const openSales = () => {
    const pipe = kpis.find((k) => k.label === "Pipeline");
    const cust = kpis.find((k) => k.label === "Active Customers");
    setPipeline(pipe?.value || "");
    setPipelineDelta(pipe?.delta != null ? String(pipe.delta) : "");
    setCustomers(cust?.value || "");
    setFunnelText(funnel.map((f) => `${f.stage}:${f.value}`).join("\n"));
    setShowSales(true);
  };

  const saveSales = async () => {
    if (!pipeline.trim()) { toast.error("Pipeline value is required"); return; }
    setBusy(true);
    try {
      const funnelRows = funnelText.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
        const [stage, value] = line.split(":").map((s) => s.trim());
        return { stage, value: parseInt(value, 10) || 0 };
      }).filter((r) => r.stage);
      await api.put("/telemetry/sales", {
        pipeline: pipeline.trim(),
        pipeline_delta: pipelineDelta === "" ? null : parseFloat(pipelineDelta),
        customers: customers.trim() || null,
        funnel: funnelRows.length ? funnelRows : null,
      });
      toast.success("Sales snapshot updated");
      setShowSales(false);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const openRisk = (r) => {
    if (r) {
      setEditingRiskId(r.id);
      setRiskForm({ name: r.name, likelihood: r.likelihood, impact: r.impact, category: r.category || "Ops" });
    } else {
      setEditingRiskId(null);
      setRiskForm(emptyRisk());
    }
    setShowRisk(true);
  };

  const saveRisk = async () => {
    if (!riskForm.name.trim()) { toast.error("Risk name required"); return; }
    setBusy(true);
    try {
      const payload = {
        name: riskForm.name.trim(),
        likelihood: Number(riskForm.likelihood),
        impact: Number(riskForm.impact),
        category: riskForm.category,
      };
      if (editingRiskId) await api.patch(`/telemetry/risks/${editingRiskId}`, payload);
      else await api.post("/telemetry/risks", payload);
      toast.success(editingRiskId ? "Risk updated" : "Risk added");
      setShowRisk(false);
      setEditingRiskId(null);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save risk");
    } finally {
      setBusy(false);
    }
  };

  const removeRisk = async (r) => {
    if (!window.confirm(`Clear risk “${r.name}”?`)) return;
    try {
      await api.delete(`/telemetry/risks/${r.id}`);
      toast.success("Risk cleared");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
    }
  };

  const actions = (
    <div className="flex items-center gap-2">
      {canOps && (
        <button data-testid="add-risk-btn" onClick={() => openRisk(null)}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-2 transition-colors hover:bg-white/5">
          <Plus className="w-4 h-4" /> Flag risk
        </button>
      )}
      {canSales && (
        <button data-testid="edit-sales-btn" onClick={openSales}
          className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 transition-colors hover:bg-gold-hover">
          <PenLine className="w-4 h-4" /> Update pipeline
        </button>
      )}
    </div>
  );

  return (
    <div>
      <PageHeader
        title="Telemetry"
        subtitle="Sales owns pipeline. Ops owns risks. Both feed the CEO Briefing."
        action={(canSales || canOps) ? actions : null}
      />

      {showSales && canSales && (
        <GlassCard className="p-5 mb-6 fade-up" data-testid="sales-form">
          <div className="flex items-center justify-between mb-4">
            <SectionLabel>Sales snapshot</SectionLabel>
            <button onClick={() => setShowSales(false)} className="text-zinc-500 hover:text-white"><X className="w-4 h-4" /></button>
          </div>
          <div className="grid sm:grid-cols-3 gap-3 mb-3">
            <input data-testid="sales-pipeline" value={pipeline} onChange={(e) => setPipeline(e.target.value)}
              placeholder="Pipeline (e.g. $1.9M)" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <input data-testid="sales-pipeline-delta" value={pipelineDelta} onChange={(e) => setPipelineDelta(e.target.value)}
              placeholder="Delta % (e.g. 12)" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <input data-testid="sales-customers" value={customers} onChange={(e) => setCustomers(e.target.value)}
              placeholder="Active customers" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
          </div>
          <textarea data-testid="sales-funnel" value={funnelText} onChange={(e) => setFunnelText(e.target.value)} rows={4}
            placeholder={"Funnel one per line: Stage:count\nLeads:1240\nQualified:486"}
            className="w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40 font-mono" />
          <div className="flex justify-end mt-3">
            <button data-testid="sales-save-btn" onClick={saveSales} disabled={busy}
              className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Saving…" : "Save sales snapshot"}
            </button>
          </div>
        </GlassCard>
      )}

      {showRisk && canOps && (
        <GlassCard className="p-5 mb-6 fade-up" data-testid="risk-form">
          <div className="flex items-center justify-between mb-4">
            <SectionLabel>{editingRiskId ? "Edit risk" : "Flag risk"}</SectionLabel>
            <button onClick={() => setShowRisk(false)} className="text-zinc-500 hover:text-white"><X className="w-4 h-4" /></button>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <input data-testid="risk-name" value={riskForm.name} onChange={(e) => setRiskForm({ ...riskForm, name: e.target.value })}
              placeholder="Risk name" className="sm:col-span-2 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <select data-testid="risk-category" value={riskForm.category} onChange={(e) => setRiskForm({ ...riskForm, category: e.target.value })}
              className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40">
              {RISK_CATS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-3">
              <input data-testid="risk-likelihood" type="number" min={1} max={5} value={riskForm.likelihood}
                onChange={(e) => setRiskForm({ ...riskForm, likelihood: e.target.value })}
                placeholder="Likelihood 1-5" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
              <input data-testid="risk-impact" type="number" min={1} max={5} value={riskForm.impact}
                onChange={(e) => setRiskForm({ ...riskForm, impact: e.target.value })}
                placeholder="Impact 1-5" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            </div>
          </div>
          <div className="flex justify-end mt-3">
            <button data-testid="risk-save-btn" onClick={saveRisk} disabled={busy}
              className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Saving…" : editingRiskId ? "Save risk" : "Add risk"}
            </button>
          </div>
        </GlassCard>
      )}

      {kpis.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {kpis.map((k, i) => (
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
      )}

      <div className="grid lg:grid-cols-2 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">MRR vs Target</SectionLabel>
          {(data.revenue_trend || []).length === 0 ? (
            <p className="text-sm text-zinc-600 py-16 text-center">No revenue trend yet</p>
          ) : (
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
          )}
        </GlassCard>

        <GlassCard className="p-5 fade-up">
          <SectionLabel className="mb-4">Sales Funnel</SectionLabel>
          {funnel.length === 0 ? (
            <p className="text-sm text-zinc-600 py-16 text-center">No funnel yet — sales can update it above</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={funnel} layout="vertical" margin={{ left: 20, right: 16 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" horizontal={false} />
                <XAxis type="number" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="stage" stroke="#a1a1aa" fontSize={11} tickLine={false} axisLine={false} width={72} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                <Bar dataKey="value" name="Count" radius={[0, 4, 4, 0]}>
                  {funnel.map((_, i) => <Cell key={i} fill={GOLD} fillOpacity={1 - i * 0.14} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </GlassCard>
      </div>

      <GlassCard className="p-5 fade-up">
        <div className="flex items-center justify-between mb-4">
          <SectionLabel>Risk Matrix</SectionLabel>
          <span className="text-xs text-zinc-600">Likelihood × Impact</span>
        </div>
        {risks.length === 0 ? (
          <p className="text-sm text-zinc-600 py-12 text-center">No risks flagged</p>
        ) : (
          <div className="grid lg:grid-cols-2 gap-6">
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ left: -8, bottom: 8 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" dataKey="x" name="Likelihood" domain={[0, 6]} ticks={[1, 2, 3, 4, 5]} stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} label={{ value: "Likelihood", position: "insideBottom", offset: -2, fill: "#52525b", fontSize: 10 }} />
                <YAxis type="number" dataKey="y" name="Impact" domain={[0, 6]} ticks={[1, 2, 3, 4, 5]} stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} label={{ value: "Impact", angle: -90, position: "insideLeft", fill: "#52525b", fontSize: 10 }} />
                <ZAxis dataKey="z" range={[80, 400]} />
                <Tooltip content={({ active, payload }) => active && payload?.length ? (
                  <div className="rounded-md border border-white/10 bg-[#141417] px-3 py-2 text-xs">
                    <p className="text-white">{payload[0].payload.name}</p>
                    <p className="text-zinc-500 font-mono mt-0.5">L{payload[0].payload.x} · I{payload[0].payload.y}</p>
                  </div>
                ) : null} />
                <Scatter data={riskData}>
                  {riskData.map((r, i) => <Cell key={i} fill={riskColor(r.z)} fillOpacity={0.85} />)}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {risks.slice().sort((a, b) => (b.likelihood * b.impact) - (a.likelihood * a.impact)).map((r) => {
                const score = r.likelihood * r.impact;
                return (
                  <div key={r.id} className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5" data-testid={`risk-${r.id}`}>
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: riskColor(score) }} />
                    <span className="text-sm text-white flex-1">{r.name}</span>
                    <span className="text-[10px] font-mono uppercase text-zinc-600">{r.category}</span>
                    <span className="font-mono text-xs" style={{ color: riskColor(score) }}>{score}</span>
                    {canOps && (
                      <div className="flex gap-0.5">
                        <button onClick={() => openRisk(r)} className="text-zinc-500 hover:text-gold p-1"><PenLine className="w-3.5 h-3.5" /></button>
                        <button onClick={() => removeRisk(r)} className="text-zinc-600 hover:text-rose-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
