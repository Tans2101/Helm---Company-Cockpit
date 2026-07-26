import { useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, PenLine, X } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const trustColor = (s) => (s >= 90 ? "text-emerald-400" : s >= 80 ? "text-gold" : "text-amber-400");
const DEPTS = ["Engineering", "Growth", "Sales", "Product", "Support", "Finance", "HR", "Ops", "General"];
const QUALITY = ["A", "A-", "B+", "B", "B-", "C"];

const emptyForm = () => ({
  name: "", role: "", department: "Engineering", trust_score: 80,
  quality: "B+", tasks_done: 0, tenure: "0y",
});

export default function People() {
  const { data, loading, reload } = useFetch("/people");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [busy, setBusy] = useState(false);

  if (loading || !data) return <LoadingScreen label="Loading roster" />;

  const canWrite = data.can_write;
  const roster = data.people || [];

  const openAdd = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowForm(true);
  };

  const openEdit = (p) => {
    setEditingId(p.id);
    setForm({
      name: p.name, role: p.role, department: p.department,
      trust_score: p.trust_score, quality: p.quality,
      tasks_done: p.tasks_done, tenure: p.tenure,
    });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name.trim() || !form.role.trim()) {
      toast.error("Name and role are required");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        ...form,
        trust_score: Number(form.trust_score) || 0,
        tasks_done: Number(form.tasks_done) || 0,
      };
      if (editingId) {
        await api.patch(`/people/${editingId}`, payload);
        toast.success("Person updated");
      } else {
        await api.post("/people", payload);
        toast.success("Person added");
      }
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm());
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (p) => {
    if (!window.confirm(`Remove ${p.name} from the roster?`)) return;
    try {
      await api.delete(`/people/${p.id}`);
      toast.success("Removed");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not remove");
    }
  };

  const actions = canWrite ? (
    <button data-testid="add-person-btn" onClick={openAdd}
      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 transition-colors hover:bg-gold-hover">
      <Plus className="w-4 h-4" /> Add person
    </button>
  ) : null;

  if (roster.length === 0 && !showForm) {
    return (
      <div>
        <PageHeader title="People" subtitle="HR owns the roster — headcount and trust feed the CEO Briefing." action={actions} />
        <EmptyState
          title="No people yet"
          body={canWrite ? "Add your first teammate to start the company roster." : "Your roster with trust scores will appear here."}
          action={canWrite ? actions : null}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="People"
        subtitle="HR owns the roster — headcount and trust feed Team Bandwidth and the CEO Briefing."
        action={actions}
      />

      {showForm && canWrite && (
        <GlassCard className="p-5 mb-6 fade-up" data-testid="person-form">
          <div className="flex items-center justify-between mb-4">
            <SectionLabel>{editingId ? "Edit person" : "Add person"}</SectionLabel>
            <button onClick={() => { setShowForm(false); setEditingId(null); }} className="text-zinc-500 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <input data-testid="person-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Full name" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <input data-testid="person-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
              placeholder="Role / title" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <select data-testid="person-department" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}
              className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40">
              {DEPTS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <select data-testid="person-quality" value={form.quality} onChange={(e) => setForm({ ...form, quality: e.target.value })}
              className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40">
              {QUALITY.map((q) => <option key={q} value={q}>Quality {q}</option>)}
            </select>
            <input data-testid="person-trust" type="number" min={0} max={100} value={form.trust_score}
              onChange={(e) => setForm({ ...form, trust_score: e.target.value })}
              placeholder="Trust score" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <input data-testid="person-tenure" value={form.tenure} onChange={(e) => setForm({ ...form, tenure: e.target.value })}
              placeholder="Tenure (e.g. 1.2y)" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            <input data-testid="person-tasks" type="number" min={0} value={form.tasks_done}
              onChange={(e) => setForm({ ...form, tasks_done: e.target.value })}
              placeholder="Tasks shipped" className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
          </div>
          <div className="flex justify-end mt-4">
            <button data-testid="person-save-btn" onClick={save} disabled={busy}
              className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 transition-colors hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Saving…" : editingId ? "Save changes" : "Add to roster"}
            </button>
          </div>
        </GlassCard>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Avg Trust Score</p>
          <p className={cn("font-mono text-3xl mt-2", trustColor(data.avg_trust))}>{data.avg_trust}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up" data-testid="people-headcount">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">People</p>
          <p className="font-mono text-3xl text-white mt-2">{roster.length}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Tasks Shipped</p>
          <p className="font-mono text-3xl text-white mt-2">{roster.reduce((a, p) => a + (p.tasks_done || 0), 0)}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Departments</p>
          <p className="font-mono text-3xl text-white mt-2">{new Set(roster.map((p) => p.department)).size}</p>
        </GlassCard>
      </div>

      <SectionLabel className="mb-4">Roster</SectionLabel>
      <div className="grid md:grid-cols-2 gap-3">
        {roster.map((p) => (
          <GlassCard key={p.id} className="p-4 fade-up transition-transform hover:-translate-y-0.5" data-testid={`person-${p.id}`}>
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center text-gold shrink-0">
                {(p.name || "?").split(" ").map((n) => n[0]).join("").slice(0, 2)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm">{p.name}</p>
                <p className="text-xs text-zinc-500">{p.role} · {p.department}</p>
              </div>
              <div className="text-right">
                <p className={cn("font-mono text-xl", trustColor(p.trust_score))}>{p.trust_score}</p>
                <p className="text-[10px] text-zinc-600 uppercase tracking-wide">trust</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-white/5 text-center">
              <div><p className="font-mono text-white text-sm">{p.quality}</p><p className="text-[10px] text-zinc-600">quality</p></div>
              <div><p className="font-mono text-white text-sm">{p.tasks_done}</p><p className="text-[10px] text-zinc-600">shipped</p></div>
              <div><p className="font-mono text-white text-sm">{p.tenure}</p><p className="text-[10px] text-zinc-600">tenure</p></div>
            </div>
            {canWrite && (
              <div className="flex justify-end gap-1 mt-3">
                <button data-testid={`edit-person-${p.id}`} onClick={() => openEdit(p)}
                  className="text-zinc-500 hover:text-gold p-1.5 rounded transition-colors">
                  <PenLine className="w-3.5 h-3.5" />
                </button>
                <button data-testid={`remove-person-${p.id}`} onClick={() => remove(p)}
                  className="text-zinc-600 hover:text-rose-400 p-1.5 rounded transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
