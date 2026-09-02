import { useState } from "react";
import { toast } from "sonner";
import { FileText, Sparkles, Plus, PenLine, Trash2, X } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const emptyReport = () => ({ title: "", type: "General", period: "", summary: "", metrics: [{ label: "", value: "" }, { label: "", value: "" }, { label: "", value: "" }] });

export default function Reports() {
  const { data, loading, error, reload } = useFetch("/reports");
  const [pack, setPack] = useState("");
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyReport());
  const [editing, setEditing] = useState(null);

  if (loading) return <LoadingScreen label="Loading reports" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load reports"
        message={fetchErrorMessage(error, "Reports data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }

  const manual = data.manual_reports || data.reports?.filter((r) => r.source === "manual") || [];
  const auto = data.auto_reports || data.reports?.filter((r) => r.source === "auto") || [];
  const canWrite = data.can_write;

  const openAdd = () => { setEditing(null); setForm(emptyReport()); setShowForm(true); };
  const openEdit = (r) => {
    setEditing(r.id);
    setForm({
      title: r.title,
      type: r.type,
      period: r.period,
      summary: r.summary,
      metrics: (r.metrics?.length ? r.metrics : emptyReport().metrics).slice(0, 3),
    });
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.title.trim()) { toast.error("Title is required"); return; }
    setBusy(true);
    const payload = {
      ...form,
      metrics: form.metrics.filter((m) => m.label?.trim() && m.value?.toString().trim()),
    };
    try {
      if (editing) await api.patch(`/reports/${editing}`, payload);
      else await api.post("/reports", payload);
      toast.success(editing ? "Report updated" : "Report added");
      setShowForm(false);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setBusy(false); }
  };

  const del = async (r) => {
    if (!window.confirm(`Delete "${r.title}"?`)) return;
    try { await api.delete(`/reports/${r.id}`); reload(); toast.success("Report removed"); }
    catch (e) { toast.error("Could not delete"); }
  };

  const generatePack = async () => {
    setBusy(true);
    try {
      const { data: res } = await api.post("/reports/weekly-pack");
      setPack(res.content);
      toast.success("Weekly CEO Pack ready");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate Weekly CEO Pack");
    } finally {
      setBusy(false);
    }
  };

  const action = canWrite ? (
    <button data-testid="add-report-btn" onClick={openAdd}
      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover">
      <Plus className="w-4 h-4" /> Add report
    </button>
  ) : null;

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Your manual reports plus live snapshots from financials, people, and tasks — each card has a clear purpose."
        action={action}
      />

      <GlassCard className="p-4 mb-6 fade-up border-white/5">
        <p className="text-sm text-zinc-400 leading-relaxed">
          <span className="text-white">How Reports works:</span> Add your own reports (sales recap, ops uptime, procurement, etc.).
          Helm also shows <span className="text-zinc-300">live auto-cards</span> computed from your workspace data.
          Automatic integrations will feed these later — for now you control the narrative.
        </p>
      </GlassCard>

      {manual.length > 0 && (
        <>
          <SectionLabel className="mb-3">Your reports</SectionLabel>
          <div className="grid md:grid-cols-3 gap-4 mb-8">
            {manual.map((r, i) => (
              <ReportCard key={r.id} report={r} index={i} canWrite={canWrite} onEdit={() => openEdit(r)} onDelete={() => del(r)} badge="Manual" />
            ))}
          </div>
        </>
      )}

      {manual.length === 0 && canWrite && (
        <div className="mb-8">
          <EmptyState title="No manual reports yet" body="Add your first report — weekly sales, production uptime, procurement status, or anything your team tracks." />
        </div>
      )}

      {auto.length > 0 && (
        <>
          <SectionLabel className="mb-3">Live from your data</SectionLabel>
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {auto.map((r, i) => (
              <ReportCard key={r.id} report={r} index={i} badge="Auto" />
            ))}
          </div>
        </>
      )}

      <GlassCard glow className="p-6 fade-up border-gold/20">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
          <div>
            <SectionLabel>Weekly CEO Pack</SectionLabel>
            <p className="text-sm text-zinc-400 max-w-xl mt-1">A board-ready weekly summary synthesized from your reports and live data.</p>
          </div>
          <button data-testid="generate-pack-btn" onClick={generatePack} disabled={busy}
            className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60 shrink-0">
            <Sparkles className="w-4 h-4" />{busy ? "Generating…" : "Generate Pack"}
          </button>
        </div>
        {pack && (
          <div className="mt-4 rounded-lg border border-white/5 bg-black/30 p-5" data-testid="pack-content">
            <pre className="whitespace-pre-wrap font-sans text-sm text-zinc-200 leading-relaxed">{pack}</pre>
          </div>
        )}
      </GlassCard>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <GlassCard className="relative w-full sm:max-w-lg m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="report-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-white font-light">{editing ? "Edit report" : "Add a report"}</h3>
              <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <label className="text-xs text-zinc-500 block">Title
                <input data-testid="report-title" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Sales Performance" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-zinc-500">Type
                  <input value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))} placeholder="Sales" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
                </label>
                <label className="text-xs text-zinc-500">Period
                  <input value={form.period} onChange={(e) => setForm((f) => ({ ...f, period: e.target.value }))} placeholder="This week" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
                </label>
              </div>
              <label className="text-xs text-zinc-500 block">Summary
                <textarea value={form.summary} onChange={(e) => setForm((f) => ({ ...f, summary: e.target.value }))} rows={3} placeholder="What happened and why it matters…" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40 resize-none" />
              </label>
              <div className="grid grid-cols-3 gap-2">
                {form.metrics.map((m, i) => (
                  <div key={i}>
                    <input value={m.label} onChange={(e) => setForm((f) => { const metrics = [...f.metrics]; metrics[i] = { ...metrics[i], label: e.target.value }; return { ...f, metrics }; })} placeholder="Metric" className="w-full rounded-md border border-white/10 bg-[#141417] text-white text-xs px-2 py-1.5 mb-1 focus:outline-none focus:border-gold/40" />
                    <input value={m.value} onChange={(e) => setForm((f) => { const metrics = [...f.metrics]; metrics[i] = { ...metrics[i], value: e.target.value }; return { ...f, metrics }; })} placeholder="Value" className="w-full rounded-md border border-white/10 bg-[#141417] text-white text-xs px-2 py-1.5 focus:outline-none focus:border-gold/40" />
                  </div>
                ))}
              </div>
            </div>
            <button data-testid="submit-report-btn" onClick={submit} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : editing ? "Save report" : "Add report"}</button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}

function ReportCard({ report: r, index, canWrite, onEdit, onDelete, badge }) {
  return (
    <GlassCard key={r.id} className="p-5 fade-up group relative" style={{ animationDelay: `${index * 60}ms` }} data-testid={`report-${r.id}`}>
      {canWrite && onEdit && (
        <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={onEdit} className="text-zinc-600 hover:text-gold p-1"><PenLine className="w-3.5 h-3.5" /></button>
          <button onClick={onDelete} className="text-zinc-600 hover:text-rose-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
        </div>
      )}
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-gold" />
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">{r.type} · {r.period}</span>
        {badge && <span className={cn("text-[9px] font-mono uppercase rounded px-1.5 py-0.5 ml-auto", badge === "Auto" ? "text-sky-400 bg-sky-400/10" : "text-gold bg-gold/10")}>{badge}</span>}
      </div>
      <h3 className="text-white font-medium pr-8">{r.title}</h3>
      <p className="text-sm text-zinc-500 mt-2 leading-relaxed">{r.summary}</p>
      {r.metrics?.length > 0 && (
        <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-white/5">
          {r.metrics.map((m) => (
            <div key={m.label}>
              <p className="font-mono text-lg text-white">{m.value}</p>
              <p className="text-[10px] text-zinc-600 uppercase tracking-wide">{m.label}</p>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  );
}
