import { useState } from "react";
import { toast } from "sonner";
import { Check, X, Sparkles, Plus, PenLine, Trash2, RefreshCw } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const statusStyle = {
  pending: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  approved: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  rejected: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  delegated: "text-sky-400 bg-sky-400/10 border-sky-400/20",
};
const emptyForm = () => ({ title: "", category: "General", description: "", recommendation: "", due: "", impact: "Medium" });

function ConfidenceBadge({ confidence, ai }) {
  if (confidence == null || confidence === "") return null;
  return (
    <span className={cn("ml-auto font-mono text-xs", ai ? "text-amber-300" : "text-gold")}>
      {confidence}%{ai ? " AI estimate" : " confidence"}
    </span>
  );
}

export default function Decisions() {
  const { data, loading, error, reload } = useFetch("/decisions");
  const { data: membersData } = useFetch("/members");
  const [busy, setBusy] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [genBusy, setGenBusy] = useState(false);

  if (loading) return <LoadingScreen label="Loading decisions" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load decisions"
        message={fetchErrorMessage(error, "Decisions data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  const canAct = data.can_act;
  const suggestions = data.suggestions || [];

  const openAdd = () => { setEditing(null); setForm(emptyForm()); setShowForm(true); };
  const openEdit = (d) => {
    setEditing(d.id);
    setForm({
      title: d.title,
      category: d.category,
      description: d.description || "",
      recommendation: d.recommendation || "",
      due: d.due === "—" ? "" : d.due,
      impact: d.impact,
    });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.title.trim()) { toast.error("Add a title"); return; }
    setSaving(true);
    // Manual decisions use Impact only — never invent a confidence %
    const payload = { ...form, confidence: null };
    try {
      if (editing) { await api.patch(`/decisions/${editing}`, payload); toast.success("Decision updated"); }
      else { await api.post("/decisions", payload); toast.success("Decision added"); }
      setShowForm(false); reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setSaving(false); }
  };

  const act = async (id, action, owner) => {
    setBusy(id);
    try { await api.post(`/decisions/${id}/action`, { action, owner }); reload(); toast.success(`Decision ${action}`); }
    catch (e) { toast.error("Action failed"); }
    finally { setBusy(null); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this decision?")) return;
    try { await api.delete(`/decisions/${id}`); reload(); toast.success("Decision removed"); }
    catch (e) { toast.error("Could not delete"); }
  };

  const approveSuggestion = async (id) => {
    setBusy(id);
    try {
      await api.post(`/decisions/suggestions/${id}/approve`);
      toast.success("Suggestion accepted — now a pending decision");
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not approve"); }
    finally { setBusy(null); }
  };

  const dismissSuggestion = async (id) => {
    setBusy(id);
    try {
      await api.post(`/decisions/suggestions/${id}/dismiss`);
      toast.success("Suggestion dismissed");
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not dismiss"); }
    finally { setBusy(null); }
  };

  const regenerate = async () => {
    setGenBusy(true);
    try {
      await api.post("/decisions/generate-suggestions");
      toast.success("Suggestions refreshed from live signals");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not regenerate suggestions");
    } finally {
      setGenBusy(false);
    }
  };

  const addBtn = canAct ? (
    <div className="flex items-center gap-2">
      <button
        data-testid="refresh-suggestions-btn"
        onClick={regenerate}
        disabled={genBusy}
        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 font-medium text-sm px-3 py-2 hover:bg-white/5 disabled:opacity-60"
      >
        <RefreshCw className={cn("w-4 h-4", genBusy && "animate-spin")} />
        {genBusy ? "Scanning…" : "Refresh suggestions"}
      </button>
      <button data-testid="new-decision-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover">
        <Plus className="w-4 h-4" /> New decision
      </button>
    </div>
  ) : null;

  const pending = data.decisions.filter((d) => d.status === "pending");
  const resolved = data.decisions.filter((d) => d.status !== "pending");

  return (
    <div>
      <PageHeader title="Decision Center" subtitle="Every open decision, ranked by impact. Helm drafts suggestions from live signals — you confirm before anything becomes a real call." action={addBtn} />

      {suggestions.length > 0 && (
        <div className="mb-8" data-testid="suggested-decisions">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-amber-300" />
            <SectionLabel>Suggested by Helm</SectionLabel>
            <span className="font-mono text-xs text-amber-300/80">{suggestions.length}</span>
          </div>
          <div className="space-y-3">
            {suggestions.map((s) => (
              <GlassCard key={s.id} className="p-5 fade-up border-amber-400/20 bg-amber-400/[0.03]" data-testid={`suggestion-${s.id}`}>
                <div className="flex flex-col lg:flex-row lg:items-start gap-5">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-amber-300 border border-amber-400/30 rounded px-1.5 py-0.5">
                        AI Suggested — verify before acting
                      </span>
                      <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 border border-white/10 rounded px-1.5 py-0.5">{s.category}</span>
                      <span className="text-[10px] font-mono text-zinc-600">Impact: {s.impact}</span>
                    </div>
                    <h3 className="text-lg text-white font-medium tracking-tight">{s.title}</h3>
                    {s.description && <p className="text-sm text-zinc-500 mt-1">{s.description}</p>}
                    {s.recommendation && (
                      <div className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/[0.04] p-3">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                          <span className="text-[11px] font-mono uppercase tracking-wider text-amber-300">Helm recommendation</span>
                          <ConfidenceBadge confidence={s.confidence} ai />
                        </div>
                        <p className="text-sm text-zinc-200 leading-relaxed">{s.recommendation}</p>
                        {s.confidence != null && (
                          <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                            <div className="h-full bg-amber-400/70 rounded-full" style={{ width: `${s.confidence}%` }} />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  {canAct && (
                    <div className="flex lg:flex-col gap-2 lg:w-40">
                      <button
                        data-testid={`approve-suggestion-${s.id}`}
                        disabled={busy === s.id}
                        onClick={() => approveSuggestion(s.id)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-gold text-black text-sm font-medium py-2 hover:bg-gold-hover disabled:opacity-50"
                      >
                        <Check className="w-4 h-4" /> Accept
                      </button>
                      <button
                        data-testid={`dismiss-suggestion-${s.id}`}
                        disabled={busy === s.id}
                        onClick={() => dismissSuggestion(s.id)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 text-zinc-400 text-sm py-2 hover:bg-white/5 hover:text-rose-400 disabled:opacity-50"
                      >
                        <X className="w-4 h-4" /> Dismiss
                      </button>
                    </div>
                  )}
                </div>
              </GlassCard>
            ))}
          </div>
        </div>
      )}

      {data.decisions.length === 0 && suggestions.length === 0 ? (
        <EmptyState title="No decisions yet" body="Log the calls that need to be made — or refresh suggestions so Helm can draft from runway, deals, tasks, and blockers."
          action={canAct ? <button data-testid="empty-new-decision-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> Log first decision</button> : null} />
      ) : (
        <>
          {pending.length > 0 && <SectionLabel className="mb-4">Open decisions</SectionLabel>}
          <div className="space-y-4">
            {pending.map((d) => {
              const isAi = d.source === "ai_suggested";
              return (
              <GlassCard key={d.id} className="p-5 fade-up" data-testid={`decision-${d.id}`}>
                <div className="flex flex-col lg:flex-row lg:items-start gap-5">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 border border-white/10 rounded px-1.5 py-0.5">{d.category}</span>
                      <span className={cn("text-[10px] font-mono uppercase tracking-wider rounded px-1.5 py-0.5 border", statusStyle[d.status])}>{d.status}</span>
                      {isAi && (
                        <span className="text-[10px] font-mono uppercase tracking-wider text-amber-300/90 border border-amber-400/20 rounded px-1.5 py-0.5">
                          From Helm
                        </span>
                      )}
                      <span className="text-[10px] font-mono text-zinc-600">Impact: {d.impact} · Due {d.due}</span>
                      {canAct && (
                        <span className="ml-auto flex items-center gap-1">
                          <button onClick={() => openEdit(d)} data-testid={`edit-decision-${d.id}`} className="text-zinc-600 hover:text-gold p-1"><PenLine className="w-3.5 h-3.5" /></button>
                          <button onClick={() => del(d.id)} data-testid={`del-decision-${d.id}`} className="text-zinc-600 hover:text-rose-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                        </span>
                      )}
                    </div>
                    <h3 className="text-lg text-white font-medium tracking-tight">{d.title}</h3>
                    {d.description && <p className="text-sm text-zinc-500 mt-1">{d.description}</p>}

                    {d.recommendation && (
                      <div className={cn("mt-4 rounded-lg border p-3", isAi ? "border-amber-400/20 bg-amber-400/[0.04]" : "border-gold/20 bg-gold/[0.04]")}>
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <Sparkles className={cn("w-3.5 h-3.5", isAi ? "text-amber-300" : "text-gold")} />
                          <span className={cn("text-[11px] font-mono uppercase tracking-wider", isAi ? "text-amber-300" : "text-gold")}>
                            {isAi ? "Helm recommendation" : "Recommendation"}
                          </span>
                          <ConfidenceBadge confidence={d.confidence} ai={isAi} />
                        </div>
                        <p className="text-sm text-zinc-200 leading-relaxed">{d.recommendation}</p>
                        {d.confidence != null && (
                          <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                            <div className={cn("h-full rounded-full", isAi ? "bg-amber-400/70" : "bg-gold")} style={{ width: `${d.confidence}%` }} />
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex lg:flex-col gap-2 lg:w-40">
                    {canAct ? (
                      <>
                        <button data-testid={`approve-${d.id}`} disabled={busy === d.id} onClick={() => act(d.id, "approved")} className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-gold text-black text-sm font-medium py-2 transition-colors hover:bg-gold-hover disabled:opacity-50"><Check className="w-4 h-4" /> Approve</button>
                        <select data-testid={`delegate-${d.id}`} disabled={busy === d.id} defaultValue="" onChange={(e) => e.target.value && act(d.id, "delegated", e.target.value)} className="flex-1 rounded-md border border-white/10 text-white text-sm py-2 px-2 bg-[#141417] transition-colors hover:bg-white/5 focus:outline-none focus:border-gold/40 disabled:opacity-50">
                          <option value="">Delegate to…</option>
                          {(membersData?.members || []).map((m) => <option key={m.membership_id} value={m.name || m.email}>{m.name || m.email}</option>)}
                        </select>
                        <button data-testid={`reject-${d.id}`} disabled={busy === d.id} onClick={() => act(d.id, "rejected")} className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 text-zinc-400 text-sm py-2 transition-colors hover:bg-white/5 hover:text-rose-400 disabled:opacity-50"><X className="w-4 h-4" /> Reject</button>
                      </>
                    ) : (
                      <p className="text-xs text-zinc-600 lg:w-40 leading-relaxed">Only owners and executives can act on decisions.</p>
                    )}
                  </div>
                </div>
              </GlassCard>
            );})}
          </div>

          {resolved.length > 0 && (
            <div className="mt-8">
              <SectionLabel className="mb-4">Recently resolved · outcome checks</SectionLabel>
              <div className="space-y-2">
                {resolved.map((d) => (
                  <div key={d.id} className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3" data-testid={`resolved-${d.id}`}>
                    <span className={cn("text-[10px] font-mono uppercase tracking-wider rounded px-1.5 py-0.5 border", statusStyle[d.status])}>{d.status}</span>
                    <span className="text-sm text-zinc-300 flex-1">{d.title}</span>
                    <span className="text-xs text-zinc-600">{d.owner ? `→ ${d.owner}` : ""}</span>
                    {canAct && <button onClick={() => del(d.id)} className="text-zinc-700 hover:text-rose-400"><Trash2 className="w-3.5 h-3.5" /></button>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6 max-h-[90vh] overflow-y-auto" data-testid="decision-form">
            <div className="flex items-center justify-between mb-5"><h3 className="text-lg text-white font-light">{editing ? "Edit decision" : "Log a decision"}</h3><button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button></div>
            <label className="text-xs text-zinc-500 block">Title
              <input data-testid="decision-title" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Approve Q3 infra budget" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
            </label>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <label className="text-xs text-zinc-500">Category
                <input data-testid="decision-category" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} placeholder="Finance" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <label className="text-xs text-zinc-500">Impact
                <select data-testid="decision-impact" value={form.impact} onChange={(e) => setForm((f) => ({ ...f, impact: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40">
                  {["High", "Medium", "Low"].map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>
              <label className="text-xs text-zinc-500">Due date
                <input data-testid="decision-due" type="date" value={form.due} onChange={(e) => setForm((f) => ({ ...f, due: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
            </div>
            <label className="text-xs text-zinc-500 block mt-3">Description
              <textarea data-testid="decision-description" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={2} placeholder="Context for the call" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40 resize-none" />
            </label>
            <label className="text-xs text-zinc-500 block mt-3">Recommendation (optional)
              <textarea data-testid="decision-recommendation" value={form.recommendation} onChange={(e) => setForm((f) => ({ ...f, recommendation: e.target.value }))} rows={2} placeholder="Your recommended course" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40 resize-none" />
            </label>
            <button data-testid="save-decision-btn" onClick={save} disabled={saving} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{saving ? "Saving…" : editing ? "Save changes" : "Log decision"}</button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
