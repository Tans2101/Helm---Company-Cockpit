import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Building2, Trash2, UserPlus, User } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { GlassCard, SectionLabel, LoadingScreen, ErrorScreen } from "@/components/kit";
import { departmentIcon } from "@/lib/departmentIcons";
import { cn } from "@/lib/utils";

export default function DepartmentsSettings() {
  const { data, loading, error, reload } = useFetch("/departments");
  const { data: membersData } = useFetch("/members");
  const [busyType, setBusyType] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [addUserId, setAddUserId] = useState("");
  const [addRole, setAddRole] = useState("member");
  const [memberBusy, setMemberBusy] = useState(false);
  const [roster, setRoster] = useState({});

  useEffect(() => {
    setRoster({});
  }, [data]);

  if (loading) return <LoadingScreen label="Loading departments" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load departments"
        message={fetchErrorMessage(error, "Department settings are unavailable.")}
        onRetry={reload}
      />
    );
  }

  if (!data.can_manage) return null;

  const departments = data.departments || [];
  const workspaceMembers = (membersData?.members || []).filter((m) => m.user_id && m.status === "active");

  const loadMembers = async (departmentId) => {
    try {
      const { data: res } = await api.get(`/departments/${departmentId}/members`);
      setRoster((r) => ({ ...r, [departmentId]: res.members || [] }));
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not load members");
    }
  };

  const toggleExpand = async (dept) => {
    if (!dept.enabled || !dept.department_id) return;
    const next = expanded === dept.department_id ? null : dept.department_id;
    setExpanded(next);
    setAddUserId("");
    setAddRole("member");
    if (next && !roster[next]) await loadMembers(next);
  };

  const toggleDept = async (dept) => {
    setBusyType(dept.type);
    try {
      if (dept.enabled) {
        const ok = window.confirm(
          `Disable ${dept.name}?\n\nThis removes its department tools data (stages, requests, tickets, onboarding, etc.) for everyone. Pipeline deals and financial entries are kept.`,
        );
        if (!ok) return;
        await api.delete(`/departments/${dept.department_id}`);
        toast.success(`${dept.name} disabled`);
        if (expanded === dept.department_id) setExpanded(null);
      } else {
        await api.post("/departments", { type: dept.type });
        toast.success(`${dept.name} enabled`);
      }
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update department");
    } finally {
      setBusyType(null);
    }
  };

  const addMember = async (departmentId) => {
    if (!addUserId) {
      toast.error("Choose a teammate");
      return;
    }
    setMemberBusy(true);
    try {
      await api.post(`/departments/${departmentId}/members`, { user_id: addUserId, role: addRole });
      toast.success("Member added");
      setAddUserId("");
      await loadMembers(departmentId);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add member");
    } finally {
      setMemberBusy(false);
    }
  };

  const removeMember = async (departmentId, userId) => {
    setMemberBusy(true);
    try {
      await api.delete(`/departments/${departmentId}/members/${userId}`);
      toast.success("Member removed");
      await loadMembers(departmentId);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not remove member");
    } finally {
      setMemberBusy(false);
    }
  };

  return (
    <GlassCard className="p-5 mb-4 fade-up" data-testid="departments-settings">
      <div className="flex items-center gap-1.5 mb-2 text-gold">
        <Building2 className="w-4 h-4" />
        <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Departments</span>
      </div>
      <p className="text-sm text-zinc-500 mb-5 leading-relaxed">
        Enable departments for your company, then assign teammates. Enabled departments appear in the sidebar for members (CEO always sees all enabled).
      </p>

      <SectionLabel className="mb-3">Add department</SectionLabel>
      <div className="space-y-2 mb-6" data-testid="department-catalog">
        {departments.map((dept) => {
          const Icon = departmentIcon(dept.icon);
          const busy = busyType === dept.type;
          return (
            <div
              key={dept.type}
              className="rounded-md border border-white/10 bg-white/[0.02] px-3 py-3"
              data-testid={`dept-row-${dept.type}`}
            >
              <div className="flex items-center gap-3">
                <Icon className="w-4 h-4 text-zinc-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{dept.name}</p>
                  <p className="text-[11px] text-zinc-600 font-mono">{dept.type}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={dept.enabled}
                  data-testid={`dept-toggle-${dept.type}`}
                  disabled={busy}
                  onClick={() => toggleDept(dept)}
                  className={cn(
                    "relative h-6 w-11 rounded-full transition-colors disabled:opacity-50",
                    dept.enabled ? "bg-gold/80" : "bg-white/10",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform",
                      dept.enabled && "translate-x-5",
                    )}
                  />
                </button>
              </div>

              {dept.enabled && (
                <div className="mt-3 pt-3 border-t border-white/5">
                  <button
                    type="button"
                    data-testid={`dept-manage-${dept.type}`}
                    onClick={() => toggleExpand(dept)}
                    className="text-xs text-zinc-400 hover:text-gold transition-colors"
                  >
                    {expanded === dept.department_id ? "Hide members" : "Manage members"}
                  </button>

                  {expanded === dept.department_id && (
                    <div className="mt-3 space-y-3" data-testid={`dept-members-${dept.type}`}>
                      {(roster[dept.department_id] || []).length === 0 ? (
                        <p className="text-xs text-zinc-600">No members yet.</p>
                      ) : (
                        <ul className="space-y-2">
                          {(roster[dept.department_id] || []).map((m) => (
                            <li key={m.user_id} className="flex items-center gap-2 text-sm">
                              {m.picture ? (
                                <img src={m.picture} alt="" className="w-6 h-6 rounded-full object-cover border border-white/10" />
                              ) : (
                                <div className="w-6 h-6 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                                  <User className="w-3 h-3 text-zinc-500" />
                                </div>
                              )}
                              <span className="flex-1 truncate text-zinc-300">{m.name || m.email}</span>
                              <span className="text-[10px] font-mono uppercase text-zinc-600">{m.role}</span>
                              <button
                                type="button"
                                data-testid={`dept-remove-${dept.type}-${m.user_id}`}
                                disabled={memberBusy}
                                onClick={() => removeMember(dept.department_id, m.user_id)}
                                className="text-zinc-600 hover:text-rose-400 p-1"
                                title="Remove"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}

                      <div className="flex flex-col sm:flex-row gap-2">
                        <select
                          data-testid={`dept-add-user-${dept.type}`}
                          value={addUserId}
                          onChange={(e) => setAddUserId(e.target.value)}
                          className="flex-1 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2"
                        >
                          <option value="">Select teammate…</option>
                          {workspaceMembers.map((m) => (
                            <option key={m.user_id} value={m.user_id}>
                              {m.name || m.email}
                            </option>
                          ))}
                        </select>
                        <select
                          data-testid={`dept-add-role-${dept.type}`}
                          value={addRole}
                          onChange={(e) => setAddRole(e.target.value)}
                          className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2"
                        >
                          <option value="member">Member</option>
                          <option value="lead">Lead</option>
                        </select>
                        <button
                          type="button"
                          data-testid={`dept-add-btn-${dept.type}`}
                          disabled={memberBusy}
                          onClick={() => addMember(dept.department_id)}
                          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-60"
                        >
                          <UserPlus className="w-3.5 h-3.5" /> Add
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
