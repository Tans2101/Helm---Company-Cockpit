import { useState } from "react";
import { toast } from "sonner";
import { Check, X, Sparkles, Plus, PenLine, Trash2 } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const statusStyle = {
  pending: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  approved: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  rejected: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  delegated: "text-sky-400 bg-sky-400/10 border-sky-400/20",
};
const emptyForm = () => ({ title: "", category: "General", description: "", recommendation: "", confidence: "", due: "", impact: "Medium" });

export default function Decisions() {
  const { data, loading, reload } = useFetch("/decisions");
  const { data: membersData } = useFetch("/members");
  const [busy, setBusy] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

  if (loading || !data) return <LoadingScreen label="Loading decisions" />;
  const canAct = data.can_act;

  const openAdd = () => { setEditing(null); setForm(emptyForm()); setShowForm(true); };
  const openEdit = (d) => {
    setEditing(d.id);
    setForm({ title: d.title, category: d.category, description: d.description || "", recommendation: d.recommendation || "", confidence: d.confidence ?? "", due: d.due === "—" ? "" : d.due, impact: d.impact });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.title.trim()) { toast.error("Add a title"); return; }
    setSaving(true);
    const payload = { ...form, confidence: form.confidence === "" ? null : parseInt(form.confidence) };
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

  const addBtn = canAct ? (
    <button data-testid="new-decision-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover">
      <Plus className="w-4 h-4" /> New decision
    </button>
  ) : null;

  const pending = data.decisions.filter((d) => d.status === "pending");
  const resolved = data.decisions.filter((d) => d.status !== "pending");

  return (
    <div>
      <PageHeader title="Decision Center" subtitle="Every open decision, ranked by impact. Log a call, get it owned, track the outcome." action={addBtn} />

      {data.decisions.length === 0 ? (
        <EmptyState title="No decisions yet" body="Log the calls that need to be made — approvals, hires, trade-offs — and track who owns each one."
          action={canAct ? <button data-testid="empty-new-decision-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> Log first decision</button> : null} />
      ) : (
        <>
          <div className="space-y-4">
            {pending.map((d) => (
              <GlassCard key={d.id} className="p-5 fade-up" data-testid={`decision-${d.id}`}>
                <div className="flex flex-col lg:flex-row lg:items-start gap-5">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 border border-white/10 rounded px-1.5 py-0.5">{d.category}</span>
                      <span className={cn("text-[10px] font-mono uppercase tracking-wider rounded px-1.5 py-0.5 border", statusStyle[d.status])}>{d.status}</span>
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
                      <div className="mt-4 rounded-lg border border-gold/20 bg-gold/[0.04] p-3">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-gold" />
                          <span className="text-[11px] font-mono uppercase tracking-wider text-gold">Recommendation</span>
                          {d.confidence != null && <span className="ml-auto font-mono text-xs text-gold">{d.confidence}% confidence</span>}
                        </div>
                        <p className="text-sm text-zinc-200 leading-relaxed">{d.recommendation}</p>
                        {d.confidence != null && (
                          <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                            <div className="h-full bg-gold rounded-full" style={{ width: `${d.confidence}%` }} />
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
            ))}
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
