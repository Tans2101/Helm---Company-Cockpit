import { useState } from "react";
import { toast } from "sonner";
import { Plus, PenLine, Trash2, X } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { DEFAULT_DEPARTMENTS, CUSTOM_DEPT } from "@/lib/departments";
import { PACKS, hasPerm } from "@/lib/access";

const emptyForm = () => ({
  name: "",
  role: "",
  department: DEFAULT_DEPARTMENTS[0],
  customDepartment: "",
  inviteToAccess: false,
  email: "",
  pack: "member",
});

function resolveDepartment(form) {
  if (form.department === CUSTOM_DEPT) return form.customDepartment.trim() || "General";
  return form.department || "General";
}

function DepartmentField({ form, setForm }) {
  const isCustom = form.department === CUSTOM_DEPT;
  return (
    <>
      <label className="text-xs text-zinc-500">Department
        <select
          data-testid="person-dept"
          value={form.department}
          onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
          className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40"
        >
          {DEFAULT_DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
          <option value={CUSTOM_DEPT}>Custom department…</option>
        </select>
      </label>
      {isCustom && (
        <label className="col-span-2 text-xs text-zinc-500">Custom department
          <input
            data-testid="person-dept-custom"
            value={form.customDepartment}
            onChange={(e) => setForm((f) => ({ ...f, customDepartment: e.target.value }))}
            placeholder="e.g. Customer Success"
            className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40"
          />
        </label>
      )}
    </>
  );
}

export default function People() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch("/people");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  if (loading) return <LoadingScreen label="Loading roster" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load roster"
        message={fetchErrorMessage(error, "People data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  const canWrite = data.can_write;
  const canInvite = data.can_invite_to_access || hasPerm(user, "members:invite");
  const deptOptions = data.departments || DEFAULT_DEPARTMENTS;
  const packOptions = PACKS.filter((p) => p.id !== "owner" || hasPerm(user, "members:manage"));

  const openAdd = () => { setEditing(null); setForm(emptyForm()); setShowForm(true); };
  const openEdit = (p) => {
    const known = deptOptions.includes(p.department);
    setEditing(p.id);
    setForm({
      name: p.name,
      role: p.role,
      department: known ? p.department : CUSTOM_DEPT,
      customDepartment: known ? "" : (p.department || ""),
      inviteToAccess: false,
      email: p.email || "",
      pack: "member",
    });
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.name.trim()) { toast.error("Name is required"); return; }
    const department = resolveDepartment(form);
    if (form.department === CUSTOM_DEPT && !department) { toast.error("Enter a custom department"); return; }
    if (!editing && form.inviteToAccess) {
      if (!form.email.trim()) { toast.error("Email is required to include in Team & Access"); return; }
    }
    setBusy(true);
    const payload = { name: form.name.trim(), role: form.role.trim(), department };
    if (!editing && form.inviteToAccess) {
      payload.invite_to_access = true;
      payload.email = form.email.trim();
      payload.pack = form.pack;
    }
    try {
      if (editing) {
        await api.patch(`/people/${editing}`, payload);
        toast.success("Person updated");
      } else {
        const { data: res } = await api.post("/people", payload);
        if (form.inviteToAccess) {
          toast.success(res.auto_joined ? "Added to roster and Team & Access" : res.email_sent ? "Added and invitation emailed" : "Added and invited to Team & Access");
        } else {
          toast.success("Person added — headcount synced");
        }
      }
      setShowForm(false);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setBusy(false); }
  };

  const del = async (p) => {
    if (p.has_access) {
      toast.error("Remove them from Team & Access first");
      return;
    }
    if (!window.confirm(`Remove ${p.name} from the roster?`)) return;
    try { await api.delete(`/people/${p.id}`); reload(); toast.success("Person removed — headcount synced"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not delete"); }
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
        <PageHeader title="People" subtitle="Your team roster — linked with Team & Access for anyone who can log in." action={action} />
        <EmptyState title="No people yet" body="Add your team here — invites from Team & Access show up automatically."
          action={canWrite ? <button data-testid="empty-add-person-btn" onClick={openAdd} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> Add first person</button> : null} />
        {showForm && <PersonForm {...{ form, setForm, submit, busy, editing, close: () => setShowForm(false), canInvite, packOptions }} />}
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="People" subtitle="Your team roster — who does what, and how headcount tracks over time." action={action} />

      <div className="grid grid-cols-2 gap-4 mb-6">
        <GlassCard className="p-5 fade-up">
          <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Headcount</p>
          <p className="font-mono text-3xl text-white mt-2" data-testid="people-headcount">{data.people.length}</p>
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
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-white text-sm">{p.name}</p>
                  {p.has_access && (
                    <span className="text-[10px] uppercase tracking-wider text-zinc-400 border border-white/10 px-1.5 py-0.5 rounded" data-testid={`person-access-${p.id}`}>
                      Team & Access
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-500">{p.role || "—"} · {p.department}</p>
              </div>
              {canWrite && (
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => openEdit(p)} data-testid={`edit-person-${p.id}`} className="text-zinc-600 hover:text-gold p-1"><PenLine className="w-3.5 h-3.5" /></button>
                  <button onClick={() => del(p)} data-testid={`del-person-${p.id}`} className="text-zinc-600 hover:text-rose-400 p-1" title={p.has_access ? "Remove from Team & Access first" : "Remove"}><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              )}
            </div>
          </GlassCard>
        ))}
      </div>

      {showForm && <PersonForm {...{ form, setForm, submit, busy, editing, close: () => setShowForm(false), canInvite, packOptions }} />}
    </div>
  );
}

function PersonForm({ form, setForm, submit, busy, editing, close, canInvite, packOptions }) {
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
          <DepartmentField form={form} setForm={setForm} />
          {!editing && canInvite && (
            <div className="col-span-2 mt-1 space-y-3 border-t border-white/5 pt-3">
              <label className="flex items-start gap-2 text-sm text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  data-testid="person-invite-access"
                  checked={form.inviteToAccess}
                  onChange={(e) => setForm((f) => ({ ...f, inviteToAccess: e.target.checked }))}
                  className="mt-1 rounded border-white/20 bg-[#141417]"
                />
                <span>
                  Also include in Team & Access
                  <span className="block text-xs text-zinc-500 mt-0.5">Sends a login invite so they can sign in.</span>
                </span>
              </label>
              {form.inviteToAccess && (
                <>
                  <label className="block text-xs text-zinc-500">Email
                    <input
                      data-testid="person-email"
                      type="email"
                      value={form.email}
                      onChange={set("email")}
                      placeholder="alex@company.com"
                      className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40"
                    />
                  </label>
                  <label className="block text-xs text-zinc-500">Access pack
                    <select
                      data-testid="person-pack"
                      value={form.pack}
                      onChange={set("pack")}
                      className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40"
                    >
                      {packOptions.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                    </select>
                  </label>
                </>
              )}
            </div>
          )}
        </div>
        <button data-testid="submit-person-btn" onClick={submit} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : editing ? "Save changes" : form.inviteToAccess ? "Add & invite" : "Add person"}</button>
      </GlassCard>
    </div>
  );
}
