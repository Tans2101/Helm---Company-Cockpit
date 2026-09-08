import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { FileText, Sparkles, Plus, PenLine, Trash2, X, Copy, Download } from "lucide-react";
import { useFetch, fetchErrorMessage, blobErrorDetail } from "@/hooks/useFetch";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const emptyReport = () => ({ title: "", type: "General", period: "", summary: "", metrics: [{ label: "", value: "" }, { label: "", value: "" }, { label: "", value: "" }] });

export default function Reports() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch("/reports");
  const [pack, setPack] = useState("");
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyTimer = useRef(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyReport());
  const [editing, setEditing] = useState(null);
  const [publishingDraftId, setPublishingDraftId] = useState(null);
  const [finPeriod, setFinPeriod] = useState("");
  const [finExporting, setFinExporting] = useState(null);

  useEffect(() => () => {
    if (copyTimer.current) clearTimeout(copyTimer.current);
  }, []);

  useEffect(() => {
    if (!data) return;
    const months = data.financial_months || [];
    const next = data.financial_latest_month || months[months.length - 1] || new Date().toISOString().slice(0, 7);
    setFinPeriod((prev) => prev || next);
  }, [data]);

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
  const drafts = data.draft_reports || [];
  const canWrite = data.can_write;
  const canGeneratePack = (user?.perms || []).includes("reports:pack");
  const canExportFinancials = Boolean(data.can_export_financials);

  const openAdd = () => {
    setEditing(null);
    setPublishingDraftId(null);
    setForm(emptyReport());
    setShowForm(true);
  };
  const openEdit = (r) => {
    setEditing(r.id);
    setPublishingDraftId(null);
    setForm({
      title: r.title,
      type: r.type,
      period: r.period,
      summary: r.summary,
      metrics: (r.metrics?.length ? r.metrics : emptyReport().metrics).slice(0, 3),
    });
    setShowForm(true);
  };
  const openPublishDraft = (d) => {
    setEditing(null);
    setPublishingDraftId(d.id);
    setForm({
      title: d.title || "",
      type: d.type || "General",
      period: d.period || "",
      summary: d.summary || "",
      metrics: (d.metrics?.length ? d.metrics : emptyReport().metrics).concat(emptyReport().metrics).slice(0, 3),
    });
    setShowForm(true);
  };
  const dismissDraft = async (d) => {
    try {
      await api.post(`/reports/drafts/${d.id}/dismiss`);
      toast.success("Draft dismissed");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not dismiss draft");
    }
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
      else await api.post("/reports", publishingDraftId ? { ...payload, from_draft_id: publishingDraftId } : payload);
      toast.success(editing ? "Report updated" : publishingDraftId ? "Report published" : "Report added");
      setShowForm(false);
      setPublishingDraftId(null);
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

  const copyPack = async () => {
    if (!pack) return;
    try {
      await navigator.clipboard.writeText(pack);
      setCopied(true);
      toast.success("Weekly pack copied");
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy — select the text instead");
    }
  };

  const downloadFinancialExport = async (kind) => {
    if (!finPeriod) return;
    setFinExporting(kind);
    try {
      const res = await api.post(
        `/reports/financial-export/${kind}`,
        { period: finPeriod },
        { responseType: "blob" },
      );
      const mime = kind === "pdf"
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const blob = new Blob([res.data], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers["content-disposition"] || "";
      const match = disposition.match(/filename="([^"]+)"/);
      a.download = match?.[1] || `Helm-Financial-Export.${kind}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(kind === "pdf" ? "PDF downloaded" : "Excel downloaded");
    } catch (e) {
      toast.error(await blobErrorDetail(e, "Could not download export"));
    } finally {
      setFinExporting(null);
    }
  };

  const downloadPdf = async () => {
    if (!pack) return;
    setExporting(true);
    try {
      const res = await api.post("/reports/weekly-pack/export-pdf", { content: pack }, { responseType: "blob" });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers["content-disposition"] || "";
      const match = disposition.match(/filename="([^"]+)"/);
      a.download = match?.[1] || "Helm-Weekly-Pack.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("PDF downloaded");
    } catch (e) {
      toast.error(await blobErrorDetail(e, "Could not download PDF"));
    } finally {
      setExporting(false);
    }
  };

  const closeForm = () => {
    setShowForm(false);
    setPublishingDraftId(null);
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
        subtitle="Your manual write-ups plus week-over-week trends from financials, people, and tasks."
        action={action}
      />

      <GlassCard className="p-4 mb-6 fade-up border-white/5">
        <p className="text-sm text-zinc-400 leading-relaxed">
          <span className="text-white">How Reports works:</span> Add your own reports (sales recap, ops uptime, procurement, etc.).
          Helm also shows <span className="text-zinc-300">week-over-week trend cards</span> — what changed since last week,
          not a restatement of numbers you already see on Financials, Team, and Tasks.
          The Weekly CEO Pack synthesizes your manual reports with those trends.
        </p>
      </GlassCard>

      {drafts.length > 0 && (
        <div className="mb-8" data-testid="department-drafts">
          <SectionLabel className="mb-3">Suggested from your departments</SectionLabel>
          <p className="text-sm text-zinc-500 mb-3">
            Rollups of completed department work this week. Review before they become a report — they are not published until you say so.
          </p>
          <div className="grid md:grid-cols-3 gap-4">
            {drafts.map((d, i) => (
              <GlassCard key={d.id} className="p-5 fade-up border-gold/20" style={{ animationDelay: `${i * 60}ms` }} data-testid={`draft-${d.id}`}>
                <div className="flex items-center gap-2 mb-3">
                  <FileText className="w-4 h-4 text-gold" />
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">{d.type} · {d.period}</span>
                  <span className="text-[9px] font-mono uppercase rounded px-1.5 py-0.5 ml-auto text-gold bg-gold/10">Draft</span>
                </div>
                <h3 className="text-white font-medium">{d.title}</h3>
                <p className="text-sm text-zinc-500 mt-2 leading-relaxed">{d.summary}</p>
                {d.metrics?.length > 0 && (
                  <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-white/5">
                    {d.metrics.map((m) => (
                      <div key={m.label}>
                        <p className="font-mono text-lg text-white">{m.value}</p>
                        <p className="text-[10px] text-zinc-600 uppercase tracking-wide">{m.label}</p>
                      </div>
                    ))}
                  </div>
                )}
                {canWrite && (
                  <div className="flex gap-2 mt-4">
                    <button
                      data-testid={`publish-draft-${d.id}`}
                      type="button"
                      onClick={() => openPublishDraft(d)}
                      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black text-sm font-medium px-3 py-2 hover:bg-gold-hover"
                    >
                      <Check className="w-3.5 h-3.5" /> Publish
                    </button>
                    <button
                      data-testid={`dismiss-draft-${d.id}`}
                      type="button"
                      onClick={() => dismissDraft(d)}
                      className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-2 hover:bg-white/5"
                    >
                      <X className="w-3.5 h-3.5" /> Dismiss
                    </button>
                  </div>
                )}
              </GlassCard>
            ))}
          </div>
        </div>
      )}

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
          <SectionLabel className="mb-3">Week-over-week trends</SectionLabel>
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {auto.map((r, i) => (
              <ReportCard key={r.id} report={r} index={i} badge="Auto" />
            ))}
          </div>
        </>
      )}

      {canExportFinancials && (
        <GlassCard className="p-6 fade-up border-gold/20 mb-6" data-testid="financial-export-card">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div>
              <SectionLabel>Financial Export</SectionLabel>
              <p className="text-sm text-zinc-400 max-w-xl mt-1">
                Income Statement and Cash Summary for a selected month — the same figures as Financials, ready for your accountant. Not a balance sheet.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-end gap-3 shrink-0">
              <label className="text-xs text-zinc-500">
                Period
                <input
                  data-testid="financial-export-period"
                  type="month"
                  value={finPeriod}
                  onChange={(e) => setFinPeriod(e.target.value)}
                  className="mt-1 block rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  data-testid="financial-export-pdf-btn"
                  type="button"
                  onClick={() => downloadFinancialExport("pdf")}
                  disabled={Boolean(finExporting)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm px-3 py-2 hover:bg-gold/15 disabled:opacity-60"
                >
                  <Download className="w-3.5 h-3.5" />
                  {finExporting === "pdf" ? "Building PDF…" : "Download PDF"}
                </button>
                <button
                  data-testid="financial-export-xlsx-btn"
                  type="button"
                  onClick={() => downloadFinancialExport("xlsx")}
                  disabled={Boolean(finExporting)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm px-3 py-2 hover:bg-gold/15 disabled:opacity-60"
                >
                  <Download className="w-3.5 h-3.5" />
                  {finExporting === "xlsx" ? "Building Excel…" : "Download Excel"}
                </button>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      <GlassCard glow className="p-6 fade-up border-gold/20">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
          <div>
            <SectionLabel>Weekly CEO Pack</SectionLabel>
            <p className="text-sm text-zinc-400 max-w-xl mt-1">A weekly summary ready to share with your leadership team, investors, or accountant.</p>
          </div>
          {canGeneratePack ? (
            <button data-testid="generate-pack-btn" onClick={generatePack} disabled={busy}
              className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60 shrink-0">
              <Sparkles className="w-4 h-4" />{busy ? "Generating…" : "Generate Pack"}
            </button>
          ) : (
            <p className="text-xs text-zinc-600 shrink-0">Owner or executive access required to generate.</p>
          )}
        </div>
        {pack && (
          <div className="mt-4 rounded-lg border border-white/5 bg-black/30 p-5" data-testid="pack-content">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <button
                data-testid="copy-pack-btn"
                type="button"
                onClick={copyPack}
                className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-2 hover:bg-white/5"
              >
                <Copy className="w-3.5 h-3.5" />
                {copied ? "Copied" : "Copy"}
              </button>
              {canGeneratePack && (
                <button
                  data-testid="download-pack-pdf-btn"
                  type="button"
                  onClick={downloadPdf}
                  disabled={exporting}
                  className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm px-3 py-2 hover:bg-gold/15 disabled:opacity-60"
                >
                  <Download className="w-3.5 h-3.5" />
                  {exporting ? "Building PDF…" : "Download PDF"}
                </button>
              )}
            </div>
            <pre className="whitespace-pre-wrap font-sans text-sm text-zinc-200 leading-relaxed">{pack}</pre>
          </div>
        )}
      </GlassCard>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={closeForm} />
          <GlassCard className="relative w-full sm:max-w-lg m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="report-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-white font-light">{editing ? "Edit report" : publishingDraftId ? "Review department draft" : "Add a report"}</h3>
              <button onClick={closeForm} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button>
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
            <button data-testid="submit-report-btn" onClick={submit} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : editing ? "Save report" : publishingDraftId ? "Publish report" : "Add report"}</button>
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
