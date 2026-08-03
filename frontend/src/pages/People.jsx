import { useState } from "react";
import { toast } from "sonner";
import { Plus, PenLine, Trash2, X } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const emptyForm = () => ({ name: "", role: "", department: "", tasks_done: 0, tenure: "" });

export default function People() {
  const { data, loading, reload } = useFetch("/people");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  if (loading || !data) return <LoadingScreen label="Loading roster" />;
  const canWrite = data.can_write;

  const openAdd = () => { setEditing(null); setForm(emptyForm()); setShowForm(true); };
  const openEdit = (p) => {
    setEditing(p.id);
    setForm({ name: p.name, role: p.role, department: p.department, tasks_done: p.tasks_done, tenure: p.tenure });
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.name.trim()) { toast.error("Name is required"); return; }
    setBusy(true);
    const payload = { ...form, tasks_done: parseInt(form.tasks_done) || 0 };
    try {
      if (editing) { await api.patch(`/people/${editing}`, payload); toast.success("Person updated"); }
      else { await api.post("/people", payload); toast.success("Person added — headcount synced"); }
      setShowForm(false);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setBusy(false); }
  };

  const del = async (p) => {
    if (!window.confirm(`Remove ${p.name} from the roster?`)) return;
    try { await api.delete(`/people/${p.id}`); reload(); toast.success("Person removed — headcount synced"); }
    catch (e) { toast.error("Could not delete"); }
  };

  const action = canWrite ? (
    <button data-testid="add-person-btn" onClick={openAdd}
      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 transition-colors hover:bg-gold-hover">
      <Plus className="w-4 h-4" /> Add person
    </button>
  ) : null;

  if (data.people.length === 0) {
    return (
      <div>
        <PageHeader title="People" subtitle="Your team roster — Helm keeps headcount in sync with the briefing." action={action} />
        <EmptyState title="No people yet" body="Add your team here — Helm keeps headcount in sync with the briefing."
          action={canWrite ? <button data-testid="empty-add-person-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> Add first person</button> : null} />
        {showForm && <PersonForm {...{ form, setForm, submit, busy, editing, close: () => setShowForm(false) }} />}
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="People" subtitle="Your team roster — who does what, and how headcount tracks over time." action={action} />

      <div className="grid grid-cols-3 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Headcount</p>
          <p className="font-mono text-3xl text-white mt-2" data-testid="people-headcount">{data.people.length}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Tasks Shipped</p>
          <p className="font-mono text-3xl text-white mt-2">{data.people.reduce((a, p) => a + (p.tasks_done || 0), 0)}</p>
        </GlassCard>
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Departments</p>
          <p className="font-mono text-3xl text-white mt-2">{new Set(data.people.map((p) => p.department)).size}</p>
        </GlassCard>
      </div>

      <SectionLabel className="mb-4">Roster</SectionLabel>
      <div className="grid md:grid-cols-2 gap-3">
        {data.people.map((p) => (
          <GlassCard key={p.id} className="p-4 fade-up transition-transform hover:-translate-y-0.5 group" data-testid={`person-${p.id}`}>
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-full bg-gold/15 border border-gold/30 flex items-center justify-center text-gold shrink-0">{p.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}</div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm">{p.name}</p>
                <p className="text-xs text-zinc-500">{p.role || "—"} · {p.department}</p>
              </div>
              {canWrite && (
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => openEdit(p)} data-testid={`edit-person-${p.id}`} className="text-zinc-600 hover:text-gold p-1"><PenLine className="w-3.5 h-3.5" /></button>
                  <button onClick={() => del(p)} data-testid={`del-person-${p.id}`} className="text-zinc-600 hover:text-rose-400 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-white/5 text-center">
              <div><p className="font-mono text-white text-sm">{p.tasks_done || 0}</p><p className="text-[10px] text-zinc-600">shipped</p></div>
              <div><p className="font-mono text-white text-sm">{p.tenure || "—"}</p><p className="text-[10px] text-zinc-600">tenure</p></div>
            </div>
          </GlassCard>
        ))}
      </div>

      {showForm && <PersonForm {...{ form, setForm, submit, busy, editing, close: () => setShowForm(false) }} />}
    </div>
  );
}

function PersonForm({ form, setForm, submit, busy, editing, close }) {
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={close} />
      <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="person-form">
        <div className="flex items-center justify-between mb-5"><h3 className="text-lg text-white font-light">{editing ? "Edit person" : "Add a person"}</h3><button onClick={close} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button></div>
        <div className="grid grid-cols-2 gap-3">
          <label className="col-span-2 text-xs text-zinc-500">Name
            <input data-testid="person-name" value={form.name} onChange={set("name")} placeholder="Jane Doe" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
          </label>
          <label className="text-xs text-zinc-500">Role
            <input data-testid="person-role" value={form.role} onChange={set("role")} placeholder="Engineer" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
          </label>
          <label className="text-xs text-zinc-500">Department
            <input data-testid="person-dept" value={form.department} onChange={set("department")} placeholder="Engineering" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
          </label>
          <label className="text-xs text-zinc-500">Tasks shipped
            <input data-testid="person-tasks" type="number" min="0" value={form.tasks_done} onChange={set("tasks_done")} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
          </label>
          <label className="text-xs text-zinc-500">Tenure
            <input data-testid="person-tenure" value={form.tenure} onChange={set("tenure")} placeholder="1.2y" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
          </label>
        </div>
        <button data-testid="submit-person-btn" onClick={submit} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : editing ? "Save changes" : "Add person"}</button>
      </GlassCard>
    </div>
  );
}
