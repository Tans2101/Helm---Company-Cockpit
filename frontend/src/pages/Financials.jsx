import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Plus, Trash2, Wallet, X, PenLine, History, Upload, Sparkles, FileText, AlertTriangle } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const GOLD = "#c9a962";
const PIE = ["#c9a962", "#8b7a4a", "#6b6b74", "#3f3f46", "#27272a", "#52525b"];
const REV_CATS = ["Subscriptions", "Enterprise", "Services", "Other"];
const EXP_CATS = ["Payroll", "Cloud/Infra", "Sales & Mktg", "G&A", "R&D Tools", "Other"];
const ALLOWED_UPLOAD_TYPES = ["application/pdf", "image/png", "image/jpeg"];
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

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

const thisMonth = () => new Date().toISOString().slice(0, 7);
const fmt = (n) => `$${Number(n || 0).toLocaleString()}`;
const emptyForm = () => ({
  type: "revenue", category: "Subscriptions", amount: "", month: thisMonth(),
  recurring: true, note: "", source_document_id: null, extract_confidence: null,
});

function mapCategory(type, raw) {
  const cats = type === "revenue" ? REV_CATS : EXP_CATS;
  if (!raw) return "Other";
  const norm = String(raw).trim().toLowerCase();
  const exact = cats.find((c) => c.toLowerCase() === norm);
  if (exact) return exact;
  const partial = cats.find((c) => norm.includes(c.toLowerCase().split("/")[0]) || c.toLowerCase().includes(norm));
  return partial || "Other";
}

function buildNote(vendor, note) {
  const parts = [];
  if (vendor) parts.push(String(vendor).trim());
  if (note && String(note).trim() && String(note).trim() !== String(vendor || "").trim()) {
    parts.push(String(note).trim());
  }
  return parts.join(" — ");
}

export default function Financials() {
  const { data, loading, reload } = useFetch("/financials");
  const { data: activityData, reload: reloadActs } = useFetch("/activities");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [cash, setCash] = useState("");
  const [gm, setGm] = useState("");
  const fileInputRef = useRef(null);

  const processBillFile = useCallback(async (file) => {
    if (!file) return;
    if (!ALLOWED_UPLOAD_TYPES.includes(file.type)) {
      toast.error("Use PDF, PNG, or JPEG only");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      toast.error("File must be 15MB or smaller");
      return;
    }
    setUploadBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data: uploaded } = await api.post("/documents/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      const { data: extracted } = await api.post(
        `/documents/${uploaded.document_id}/extract`,
        {},
        { timeout: 120000 },
      );
      if (extracted?.error === "not_financial") {
        toast.error("This doesn't look like a bill or invoice — upload a financial document only.");
        return;
      }
      const entryType = extracted.type === "revenue" ? "revenue" : "expense";
      setForm({
        type: entryType,
        category: mapCategory(entryType, extracted.category),
        amount: extracted.amount != null ? String(extracted.amount) : "",
        month: extracted.month || thisMonth(),
        recurring: entryType === "revenue",
        note: buildNote(extracted.vendor, extracted.note),
        source_document_id: uploaded.document_id,
        extract_confidence: extracted.confidence || "medium",
      });
      setShowForm(true);
      toast.success("Review the extracted entry and save when it looks right");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not process document");
    } finally {
      setUploadBusy(false);
      setDragOver(false);
    }
  }, []);

  const onFilePick = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    processBillFile(file);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    processBillFile(file);
  };

  const openDocument = async (docId) => {
    try {
      const { data: doc } = await api.get(`/documents/${docId}`);
      if (doc?.presigned_url) window.open(doc.presigned_url, "_blank", "noopener,noreferrer");
      else toast.error("Could not open document");
    } catch {
      toast.error("Could not open document");
    }
  };

  if (loading || !data) return <LoadingScreen label="Loading financials" />;

  const canWrite = data.can_write;
  const finActs = (activityData?.items || activityData?.activities || []).filter((a) => a.module === "financials").slice(0, 5);

  const submitEntry = async () => {
    if (!form.amount || !form.month) { toast.error("Add an amount and month"); return; }
    setBusy(true);
    try {
      const payload = {
        type: form.type,
        category: form.category,
        amount: parseFloat(form.amount),
        month: form.month,
        recurring: form.recurring,
        note: form.note,
      };
      if (form.source_document_id) payload.source_document_id = form.source_document_id;
      await api.post("/financials/entries", payload);
      toast.success("Entry logged");
      setForm(emptyForm());
      setShowForm(false);
      reload();
      reloadActs();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setBusy(false); }
  };

  const del = async (id) => {
    if (!window.confirm("Remove this entry? This can't be undone.")) return;
    try { await api.delete(`/financials/entries/${id}`); reload(); reloadActs(); toast.success("Entry removed"); }
    catch (e) { toast.error("Could not delete"); }
  };

  const saveSettings = async () => {
    setBusy(true);
    try {
      await api.put("/financials/settings", { cash: parseFloat(cash || 0), gross_margin: gm ? parseFloat(gm) : null });
      toast.success("Updated");
      setShowSettings(false);
      reload();
      reloadActs();
    } catch (e) { toast.error("Could not save"); }
    finally { setBusy(false); }
  };

  const openSettings = () => {
    setCash(String(data.settings?.cash ?? ""));
    setGm(data.settings?.gross_margin != null ? String(data.settings.gross_margin) : "");
    setShowSettings(true);
  };

  const headline = [
    { label: "MRR", value: data.mrr }, { label: "ARR", value: data.arr },
    { label: "Runway", value: data.runway_months ? `${data.runway_months}mo` : "—" },
    { label: "Net Burn", value: data.burn }, { label: "Cash", value: data.cash },
    { label: "Gross Margin", value: data.gross_margin },
  ];

  const actions = canWrite ? (
    <div className="flex flex-wrap items-center gap-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
        className="hidden"
        data-testid="bill-file-input"
        onChange={onFilePick}
      />
      <button
        type="button"
        data-testid="upload-bill-btn"
        disabled={uploadBusy}
        onClick={() => fileInputRef.current?.click()}
        className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold font-medium text-sm px-3 py-2 transition-colors hover:bg-gold/15 disabled:opacity-60"
      >
        <Upload className="w-4 h-4" />
        {uploadBusy ? "Reading bill…" : "Upload a bill"}
      </button>
      <button data-testid="add-entry-btn" onClick={() => { setForm(emptyForm()); setShowForm(true); }}
        className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 transition-colors hover:bg-gold-hover">
        <Plus className="w-4 h-4" /> Log entry
      </button>
    </div>
  ) : null;

  return (
    <div>
      <PageHeader title="Financials" subtitle="Your finance team logs revenue and expenses here — Helm turns it into live MRR, runway and burn across the whole cockpit." action={actions} />

      {canWrite && (
        <div
          data-testid="bill-dropzone"
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={cn(
            "mb-6 rounded-xl border border-dashed px-5 py-6 text-center transition-colors fade-up",
            dragOver ? "border-gold/50 bg-gold/[0.06]" : "border-white/10 bg-white/[0.02]",
            uploadBusy && "opacity-70 pointer-events-none",
          )}
        >
          <div className="flex flex-col items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
              <FileText className="w-5 h-5 text-gold" />
            </div>
            <p className="text-sm text-zinc-300">Drop a bill, receipt, or invoice here</p>
            <p className="text-xs text-zinc-600">PDF, PNG, or JPEG · up to 15MB · Claude reads it and pre-fills an entry for you to confirm</p>
          </div>
        </div>
      )}

      {!data.has_data ? (
        <EmptyState icon={Wallet} title="No financials logged yet"
          body="Log your revenue and expenses and Helm computes MRR, ARR, runway and burn automatically."
          action={canWrite ? (
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button data-testid="empty-upload-bill-btn" onClick={() => fileInputRef.current?.click()} disabled={uploadBusy}
                className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold font-medium text-sm px-4 py-2 hover:bg-gold/15 disabled:opacity-60">
                <Upload className="w-4 h-4" /> Upload a bill
              </button>
              <button data-testid="empty-add-entry-btn" onClick={() => { setForm(emptyForm()); setShowForm(true); }}
                className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover">
                <Plus className="w-4 h-4" /> Log first entry
              </button>
            </div>
          ) : <p className="text-sm text-zinc-600">Ask a workspace owner or finance teammate to add data.</p>}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
            {headline.map((h) => (
              <GlassCard key={h.label} className="p-4 fade-up" data-testid={`fin-${h.label}`}>
                <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">{h.label}</p>
                <p className="font-mono text-2xl text-white mt-2">{h.value}</p>
              </GlassCard>
            ))}
          </div>

          {finActs.length > 0 && (
            <GlassCard className="p-4 mb-6 fade-up" data-testid="financials-activity">
              <div className="flex items-center gap-1.5 mb-3 text-gold">
                <History className="w-3.5 h-3.5" />
                <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Recent activity</span>
              </div>
              <div className="space-y-2">
                {finActs.map((a) => (
                  <div key={a.activity_id} className="flex items-center gap-2 text-sm" data-testid={`fin-activity-${a.activity_id}`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-gold/60 shrink-0" />
                    <span className="text-zinc-300 flex-1 truncate">{a.summary}</span>
                    <span className="text-xs text-zinc-600 font-mono shrink-0 hidden sm:inline">{a.actor_name} · {a.ago}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}

          <div className="grid lg:grid-cols-3 gap-4 mb-6">
            <GlassCard className="p-5 lg:col-span-2 fade-up">
              <SectionLabel className="mb-4">Revenue vs Expenses</SectionLabel>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={data.revenue_series} margin={{ left: -8, right: 8, top: 8 }}>
                  <defs><linearGradient id="rev" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={GOLD} stopOpacity={0.35} /><stop offset="100%" stopColor={GOLD} stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="month" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v / 1000}k`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="revenue" name="Revenue" stroke={GOLD} strokeWidth={2} fill="url(#rev)" />
                  <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#71717a" strokeWidth={1.5} fill="none" strokeDasharray="4 4" />
                </AreaChart>
              </ResponsiveContainer>
            </GlassCard>

            <GlassCard className="p-5 fade-up">
              <div className="flex items-center justify-between mb-2">
                <SectionLabel>Cash & margin</SectionLabel>
                {canWrite && <button data-testid="edit-settings-btn" onClick={openSettings} className="text-zinc-500 hover:text-gold"><PenLine className="w-3.5 h-3.5" /></button>}
              </div>
              {data.expense_breakdown.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={170}>
                    <PieChart><Pie data={data.expense_breakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={44} outerRadius={72} paddingAngle={2} stroke="none">{data.expense_breakdown.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}</Pie><Tooltip content={<ChartTooltip />} /></PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-1 mt-1">
                    {data.expense_breakdown.map((e, i) => (
                      <div key={e.name} className="flex items-center gap-2 text-xs"><span className="w-2 h-2 rounded-sm" style={{ background: PIE[i % PIE.length] }} /><span className="text-zinc-400 flex-1">{e.name}</span><span className="font-mono text-zinc-300">{e.value}%</span></div>
                    ))}
                  </div>
                </>
              ) : <p className="text-sm text-zinc-600 py-8 text-center">Log expenses to see the breakdown.</p>}
            </GlassCard>
          </div>

          {data.scenarios.length > 0 && (
            <div className="grid lg:grid-cols-3 gap-4 mb-6">
              <GlassCard className="p-5 lg:col-span-2 fade-up">
                <SectionLabel className="mb-4">Monthly Net Burn</SectionLabel>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data.burn_series} margin={{ left: -8, right: 8 }}>
                    <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="month" stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke="#52525b" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v / 1000}k`} />
                    <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                    <Bar dataKey="burn" name="Net burn" fill={GOLD} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </GlassCard>
              <GlassCard className="p-5 fade-up">
                <SectionLabel className="mb-4">Runway Scenarios</SectionLabel>
                <div className="space-y-3">
                  {data.scenarios.map((s) => (
                    <div key={s.name} className="rounded-lg border border-white/5 bg-white/[0.02] p-3" data-testid={`scenario-${s.name}`}>
                      <div className="flex items-center justify-between"><span className="text-sm text-white">{s.name}</span><span className="font-mono text-gold text-sm">{s.runway}mo</span></div>
                      <p className="text-xs text-zinc-500 mt-1">{s.desc}</p>
                      <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden"><div className="h-full bg-gold/70 rounded-full" style={{ width: `${Math.min(s.runway / 36 * 100, 100)}%` }} /></div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </div>
          )}

          <GlassCard className="p-5 fade-up">
            <SectionLabel className="mb-4">Ledger · {data.entries.length} entries</SectionLabel>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-zinc-600 border-b border-white/5">
                    <th className="py-2 pr-4 font-medium">Month</th><th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Category</th><th className="py-2 pr-4 font-medium text-right">Amount</th>
                    <th className="py-2 pr-4 font-medium">Source</th><th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.entries.map((e) => (
                    <tr key={e.id} className="border-b border-white/[0.03]" data-testid={`entry-${e.id}`}>
                      <td className="py-2.5 pr-4 font-mono text-zinc-400">{e.month}</td>
                      <td className="py-2.5 pr-4"><span className={cn("text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5", e.type === "revenue" ? "text-emerald-400 bg-emerald-400/10" : "text-rose-400 bg-rose-400/10")}>{e.type}</span></td>
                      <td className="py-2.5 pr-4 text-zinc-300">{e.category}{e.recurring && <span className="ml-1.5 text-[9px] text-gold/70 font-mono">MRR</span>}</td>
                      <td className="py-2.5 pr-4 text-right font-mono text-white">{fmt(e.amount)}</td>
                      <td className="py-2.5 pr-4">
                        {e.source === "ai_upload" && e.source_document_id ? (
                          <button
                            type="button"
                            data-testid={`entry-doc-${e.id}`}
                            onClick={() => openDocument(e.source_document_id)}
                            className="inline-flex items-center gap-1 text-[10px] font-mono text-gold hover:text-gold-hover transition-colors"
                            title="View original document"
                          >
                            <Sparkles className="w-3 h-3" /> AI upload
                          </button>
                        ) : (
                          <span className="text-[10px] font-mono text-zinc-600">{e.source}</span>
                        )}
                      </td>
                      <td className="py-2.5 text-right">{canWrite && <button onClick={() => del(e.id)} data-testid={`del-${e.id}`} className="text-zinc-600 hover:text-rose-400"><Trash2 className="w-3.5 h-3.5" /></button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="entry-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-white font-light">
                {form.source_document_id ? "Confirm extracted entry" : "Log a financial entry"}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            {form.extract_confidence === "low" && (
              <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-200" data-testid="low-confidence-banner">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>Double-check this one — I wasn&apos;t fully sure.</span>
              </div>
            )}
            {form.source_document_id && (
              <p className="mb-4 text-xs text-zinc-500 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-gold" />
                Pre-filled from your upload — edit anything before saving.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 flex gap-2">
                {["revenue", "expense"].map((t) => (
                  <button key={t} data-testid={`type-${t}`} onClick={() => setForm((f) => ({ ...f, type: t, category: t === "revenue" ? REV_CATS[0] : EXP_CATS[0] }))}
                    className={cn("flex-1 rounded-md py-2 text-sm capitalize transition-colors border", form.type === t ? "bg-gold/10 border-gold/40 text-white" : "border-white/10 text-zinc-400 hover:bg-white/5")}>{t}</button>
                ))}
              </div>
              <label className="col-span-2 text-xs text-zinc-500">Category
                <select data-testid="entry-category" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40">
                  {(form.type === "revenue" ? REV_CATS : EXP_CATS).map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label className="text-xs text-zinc-500">Amount (USD)
                <input data-testid="entry-amount" type="number" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} placeholder="50000" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <label className="text-xs text-zinc-500">Month
                <input data-testid="entry-month" type="month" value={form.month} onChange={(e) => setForm((f) => ({ ...f, month: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              {form.type === "revenue" && (
                <label className="col-span-2 flex items-center gap-2 text-sm text-zinc-300 mt-1">
                  <input data-testid="entry-recurring" type="checkbox" checked={form.recurring} onChange={(e) => setForm((f) => ({ ...f, recurring: e.target.checked }))} className="accent-gold w-4 h-4" />
                  Recurring (counts toward MRR)
                </label>
              )}
              <label className="col-span-2 text-xs text-zinc-500">Note (optional)
                <input data-testid="entry-note" value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
            </div>
            <button data-testid="submit-entry-btn" onClick={submitEntry} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : "Save entry"}</button>
          </GlassCard>
        </div>
      )}

      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowSettings(false)} />
          <GlassCard className="relative w-full max-w-sm m-4 rounded-2xl p-6" data-testid="settings-form">
            <div className="flex items-center justify-between mb-5"><h3 className="text-lg text-white font-light">Cash & margin</h3><button onClick={() => setShowSettings(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button></div>
            <label className="text-xs text-zinc-500 block">Cash in bank (USD)
              <input data-testid="settings-cash" type="number" value={cash} onChange={(e) => setCash(e.target.value)} placeholder="3100000" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
            </label>
            <label className="text-xs text-zinc-500 block mt-3">Gross margin % (optional)
              <input data-testid="settings-gm" type="number" value={gm} onChange={(e) => setGm(e.target.value)} placeholder="74" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
            </label>
            <button data-testid="save-settings-btn" onClick={saveSettings} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : "Save"}</button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
