import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Plus, PenLine, Trash2, X, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { fetchErrorMessage } from "@/hooks/useFetch";
import { cn } from "@/lib/utils";

const stageStyle = {
  lead: "text-zinc-300 bg-white/5",
  qualified: "text-sky-300 bg-sky-400/10",
  proposal: "text-violet-300 bg-violet-400/10",
  negotiation: "text-gold bg-gold/10",
  won: "text-emerald-300 bg-emerald-400/10",
  lost: "text-rose-300 bg-rose-400/10",
};
const money = (n, sym = "$") => sym + (n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : n);
const emptyForm = () => ({ name: "", company: "", value: "", stage: "lead", owner_name: "", close_date: "" });
const PAGE_LIMIT = 200;

export default function Pipeline() {
  const [deals, setDeals] = useState([]);
  const [meta, setMeta] = useState(null);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [busy, setBusy] = useState(false);

  const fetchPage = useCallback(async (before = null, append = false) => {
    const params = { limit: PAGE_LIMIT };
    if (before) params.before = before;
    const { data } = await api.get("/deals", { params });
    const page = data.items || data.deals || [];
    setDeals((prev) => (append ? [...prev, ...page] : page));
    setMeta({
      can_write: data.can_write,
      metrics: data.metrics,
      stages: data.stages,
      currency: data.currency || "usd",
      currency_symbol: data.currency_symbol || "$",
    });
    setNextCursor(data.next_cursor ?? null);
    return data;
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      await fetchPage();
    } catch (e) {
      setLoadError(e);
      toast.error(fetchErrorMessage(e, "Could not load pipeline"));
    } finally {
      setLoading(false);
    }
  }, [fetchPage]);

  useEffect(() => {
    reload();
  }, [reload]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      await fetchPage(nextCursor, true);
    } catch {
      toast.error("Could not load more deals");
    } finally {
      setLoadingMore(false);
    }
  };

  if (loading) return <LoadingScreen label="Loading pipeline" />;
  if (loadError || !meta) {
    return (
      <ErrorScreen
        label="Could not load pipeline"
        message={fetchErrorMessage(loadError, "Pipeline data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  const canWrite = meta.can_write;
  const m = meta.metrics;
  const sym = meta.currency_symbol || "$";

  const openAdd = () => { setEditing(null); setForm(emptyForm()); setShowForm(true); };
  const openEdit = (d) => {
    setEditing(d.id);
    setForm({ name: d.name, company: d.company || "", value: d.value, stage: d.stage, owner_name: d.owner_name || "", close_date: d.close_date || "" });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name.trim()) { toast.error("Deal name required"); return; }
    setBusy(true);
    const payload = { ...form, value: parseFloat(form.value) || 0 };
    try {
      if (editing) { await api.patch(`/deals/${editing}`, payload); toast.success("Deal updated"); }
      else { await api.post("/deals", payload); toast.success("Deal added to pipeline"); }
      setShowForm(false); reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setBusy(false); }
  };

  const changeStage = async (d, stage) => {
    try { await api.patch(`/deals/${d.id}`, { name: d.name, company: d.company, value: d.value, stage, owner_name: d.owner_name, close_date: d.close_date }); reload(); }
    catch (e) { toast.error("Could not update stage"); }
  };
  const del = async (d) => {
    if (!window.confirm(`Delete ${d.name}?`)) return;
    try { await api.delete(`/deals/${d.id}`); reload(); toast.success("Deal removed"); }
    catch (e) { toast.error("Could not delete"); }
  };

  const action = canWrite ? (
    <button data-testid="add-deal-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover">
      <Plus className="w-4 h-4" /> New deal
    </button>
  ) : null;

  return (
    <div>
      <PageHeader title="Sales Pipeline" subtitle="Log deals and stages — pipeline signals roll straight into the CEO Briefing." action={action} />

      {deals.length === 0 ? (
        <EmptyState icon={TrendingUp} title="No deals yet" body="Add your first deal — as it moves through stages, the CEO sees it in the morning briefing."
          action={canWrite ? <button data-testid="empty-add-deal-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> Add first deal</button> : null} />
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <GlassCard className="p-5 fade-up"><p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Open Pipeline</p><p className="font-mono text-2xl text-white mt-2" data-testid="metric-open">{money(m.open_value, sym)}</p></GlassCard>
            <GlassCard className="p-5 fade-up"><p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Weighted</p><p className="font-mono text-2xl text-gold mt-2">{money(m.weighted_value, sym)}</p></GlassCard>
            <GlassCard className="p-5 fade-up"><p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Won</p><p className="font-mono text-2xl text-emerald-400 mt-2">{money(m.won_value, sym)}</p></GlassCard>
            <GlassCard className="p-5 fade-up"><p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Open Deals</p><p className="font-mono text-2xl text-white mt-2">{m.open_count}</p></GlassCard>
          </div>

          <div className="space-y-6">
            {m.by_stage.filter((s) => s.count > 0).map((s) => (
              <div key={s.stage}>
                <div className="flex items-center gap-2 mb-2">
                  <SectionLabel>{s.label}</SectionLabel>
                  <span className="text-xs font-mono text-zinc-600">{s.count} · {money(s.value, sym)}</span>
                </div>
                <div className="space-y-2">
                  {deals.filter((d) => d.stage === s.stage).map((d) => (
                    <GlassCard key={d.id} className="p-4 fade-up flex items-center gap-4 group" data-testid={`deal-${d.id}`}>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white truncate">{d.name}</p>
                        <p className="text-xs text-zinc-500 truncate">
                          {d.company || "—"}
                          {d.owner_name ? ` · Owner ${d.owner_name}` : ""}
                          {d.close_date ? ` · close ${d.close_date}` : ""}
                        </p>
                        {d.created_by_name ? (
                          <p className="text-[11px] text-zinc-600 mt-0.5" data-testid={`deal-added-by-${d.id}`}>
                            Added by {d.created_by_name}
                          </p>
                        ) : null}
                      </div>
                      <span className="font-mono text-sm text-white shrink-0">{money(d.value, sym)}</span>
                      {canWrite ? (
                        <select value={d.stage} onChange={(e) => changeStage(d, e.target.value)} data-testid={`deal-stage-${d.id}`}
                          className={cn("text-[11px] font-mono rounded px-2 py-1 border border-white/10 bg-[#141417] focus:outline-none focus:border-gold/40", stageStyle[d.stage])}>
                          {meta.stages.map((st) => <option key={st.id} value={st.id}>{st.label}</option>)}
                        </select>
                      ) : (
                        <span className={cn("text-[10px] font-mono uppercase rounded px-1.5 py-0.5", stageStyle[d.stage])}>{s.label}</span>
                      )}
                      {canWrite && (
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => openEdit(d)} data-testid={`edit-deal-${d.id}`} className="text-zinc-600 hover:text-gold p-1"><PenLine className="w-3.5 h-3.5" /></button>
                          <button onClick={() => del(d)} data-testid={`del-deal-${d.id}`} className="text-zinc-600 hover:text-rose-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      )}
                    </GlassCard>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {nextCursor && (
            <div className="mt-8 flex justify-center">
              <button
                type="button"
                data-testid="load-more-deals-btn"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-gold/30 hover:text-white disabled:opacity-60"
              >
                {loadingMore ? "Loading…" : "Load more deals"}
              </button>
            </div>
          )}
        </>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="deal-form">
            <div className="flex items-center justify-between mb-5"><h3 className="text-lg text-white font-light">{editing ? "Edit deal" : "New deal"}</h3><button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button></div>
            <label className="text-xs text-zinc-500 block">Deal name
              <input data-testid="deal-name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Acme Corp — Enterprise" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
            </label>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <label className="text-xs text-zinc-500">Company
                <input data-testid="deal-company" value={form.company} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} placeholder="Acme" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <label className="text-xs text-zinc-500">Value ({sym})
                <input data-testid="deal-value" type="number" min="0" value={form.value} onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))} placeholder="25000" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <label className="text-xs text-zinc-500">Stage
                <select data-testid="deal-stage" value={form.stage} onChange={(e) => setForm((f) => ({ ...f, stage: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40">
                  {meta.stages.map((st) => <option key={st.id} value={st.id}>{st.label}</option>)}
                </select>
              </label>
              <label className="text-xs text-zinc-500">Expected close
                <input data-testid="deal-close" type="date" value={form.close_date} onChange={(e) => setForm((f) => ({ ...f, close_date: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <label className="text-xs text-zinc-500 col-span-2">Owner
                <input data-testid="deal-owner" value={form.owner_name} onChange={(e) => setForm((f) => ({ ...f, owner_name: e.target.value }))} placeholder="Rep name" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
            </div>
            <button data-testid="save-deal-btn" onClick={save} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : editing ? "Save changes" : "Add deal"}</button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
