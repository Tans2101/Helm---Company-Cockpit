import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, ChevronUp, ChevronDown, Trash2, X, User } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  not_started: { label: "Not started", className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30" },
  in_progress: { label: "In progress", className: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  blocked: { label: "Blocked", className: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
  done: { label: "Done", className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.not_started;
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide border", meta.className)}>
      {meta.label}
    </span>
  );
}

function AssigneeChips({ assignees }) {
  const list = assignees || [];
  if (!list.length) return <span className="text-xs text-zinc-600">Unassigned</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {list.map((a) => (
        <span
          key={a.user_id}
          className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] pl-0.5 pr-2 py-0.5 text-[11px] text-zinc-300"
          title={a.email || a.name}
        >
          {a.picture ? (
            <img src={a.picture} alt="" className="w-4 h-4 rounded-full object-cover" />
          ) : (
            <span className="w-4 h-4 rounded-full bg-white/10 flex items-center justify-center">
              <User className="w-2.5 h-2.5 text-zinc-500" />
            </span>
          )}
          <span className="truncate max-w-[7rem]">{a.name || a.email || "Teammate"}</span>
        </span>
      ))}
    </div>
  );
}

export default function Production() {
  const { data, loading, error, reload } = useFetch("/production/stages");
  const { data: membersData } = useFetch("/members");
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");

  const stages = data?.stages || [];
  const selected = stages.find((s) => s.id === selectedId) || null;

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      return;
    }
    setDraft({
      name: selected.name || "",
      status: selected.status || "not_started",
      notes: selected.notes || "",
      assigned_user_ids: [...(selected.assigned_user_ids || [])],
    });
  }, [selectedId, selected?.updated_at]);

  if (loading) return <LoadingScreen label="Loading production chain" />;
  if (error) {
    const status = error?.response?.status;
    if (status === 403) {
      return (
        <ErrorScreen
          label="Access denied"
          message="You are not a member of Production. Ask your CEO to add you."
          onRetry={reload}
        />
      );
    }
    if (status === 404) {
      return (
        <ErrorScreen
          label="Production not enabled"
          message="Enable Production under Settings → Departments first."
          onRetry={reload}
        />
      );
    }
    return (
      <ErrorScreen
        label="Could not load Production"
        message={fetchErrorMessage(error, "Production data is unavailable.")}
        onRetry={reload}
      />
    );
  }

  const canStructure = data?.can_edit_structure;
  const workspaceMembers = (membersData?.members || []).filter((m) => m.user_id && m.status === "active");

  const createStage = async () => {
    if (!newName.trim()) {
      toast.error("Stage name is required");
      return;
    }
    setBusy(true);
    try {
      const { data: res } = await api.post("/production/stages", { name: newName.trim() });
      toast.success("Stage added");
      setNewName("");
      setAdding(false);
      await reload();
      if (res?.stage?.id) setSelectedId(res.stage.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add stage");
    } finally {
      setBusy(false);
    }
  };

  const saveStage = async () => {
    if (!selected || !draft) return;
    setBusy(true);
    try {
      const body = {
        status: draft.status,
        notes: draft.notes,
        assigned_user_ids: draft.assigned_user_ids,
      };
      if (canStructure && draft.name !== selected.name) body.name = draft.name;
      const { data: res } = await api.patch(`/production/stages/${selected.id}`, body);
      toast.success("Stage updated");
      await reload();
      if (res?.stage?.id) setSelectedId(res.stage.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update stage");
    } finally {
      setBusy(false);
    }
  };

  const deleteStage = async (stage) => {
    if (!window.confirm(`Delete stage “${stage.name}”?`)) return;
    setBusy(true);
    try {
      await api.delete(`/production/stages/${stage.id}`);
      toast.success("Stage deleted");
      if (selectedId === stage.id) setSelectedId(null);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
    } finally {
      setBusy(false);
    }
  };

  const moveStage = async (stage, direction) => {
    const idx = stages.findIndex((s) => s.id === stage.id);
    const swap = idx + direction;
    if (idx < 0 || swap < 0 || swap >= stages.length) return;
    const next = stages.map((s) => s.id);
    [next[idx], next[swap]] = [next[swap], next[idx]];
    setBusy(true);
    try {
      await api.patch("/production/stages/reorder", { stage_ids: next });
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not reorder");
    } finally {
      setBusy(false);
    }
  };

  const toggleAssignee = (userId) => {
    setDraft((d) => {
      if (!d) return d;
      const has = d.assigned_user_ids.includes(userId);
      return {
        ...d,
        assigned_user_ids: has
          ? d.assigned_user_ids.filter((id) => id !== userId)
          : [...d.assigned_user_ids, userId],
      };
    });
  };

  const action = canStructure ? (
    <button
      type="button"
      data-testid="add-production-stage-btn"
      onClick={() => setAdding(true)}
      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover"
    >
      <Plus className="w-4 h-4" /> Add stage
    </button>
  ) : null;

  return (
    <div>
      <PageHeader
        title={data?.name || "Production"}
        subtitle="Ordered production chain — status and owners at a glance."
        action={action}
      />

      {stages.length === 0 ? (
        <EmptyState
          title="No stages yet"
          body={canStructure ? "Add the first stage to start the production chain." : "Ask a Production lead or the CEO to set up the chain."}
          action={canStructure ? (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"
            >
              <Plus className="w-4 h-4" /> Add first stage
            </button>
          ) : null}
        />
      ) : (
        <div className="space-y-3 mb-6" data-testid="production-chain">
          {stages.map((stage, index) => (
            <GlassCard
              key={stage.id}
              data-testid={`production-stage-${stage.id}`}
              className={cn(
                "p-4 fade-up cursor-pointer transition-colors hover:border-gold/30",
                selectedId === stage.id && "border-gold/40 bg-gold/[0.04]",
              )}
              onClick={() => setSelectedId(stage.id)}
            >
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-md border border-white/10 bg-white/[0.03] flex items-center justify-center font-mono text-xs text-zinc-400 shrink-0">
                  {index + 1}
                </div>
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm text-white truncate">{stage.name}</p>
                    <StatusBadge status={stage.status} />
                  </div>
                  <AssigneeChips assignees={stage.assignees} />
                </div>
                {canStructure && (
                  <div className="flex flex-col gap-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      disabled={busy || index === 0}
                      data-testid={`stage-up-${stage.id}`}
                      onClick={() => moveStage(stage, -1)}
                      className="p-1 text-zinc-600 hover:text-white disabled:opacity-30"
                      title="Move up"
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      disabled={busy || index === stages.length - 1}
                      data-testid={`stage-down-${stage.id}`}
                      onClick={() => moveStage(stage, 1)}
                      className="p-1 text-zinc-600 hover:text-white disabled:opacity-30"
                      title="Move down"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {selected && draft && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setSelectedId(null)} />
          <GlassCard className="relative w-full sm:max-w-lg m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="production-stage-panel">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-white font-light">Stage details</h3>
              <button type="button" onClick={() => setSelectedId(null)} className="text-zinc-500 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3">
              <label className="block text-xs text-zinc-500">Name
                <input
                  data-testid="stage-name-input"
                  value={draft.name}
                  disabled={!canStructure}
                  onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 disabled:opacity-60"
                />
              </label>
              <label className="block text-xs text-zinc-500">Status
                <select
                  data-testid="stage-status-select"
                  value={draft.status}
                  onChange={(e) => setDraft((d) => ({ ...d, status: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2"
                >
                  {Object.entries(STATUS_META).map(([id, meta]) => (
                    <option key={id} value={id}>{meta.label}</option>
                  ))}
                </select>
              </label>
              <div>
                <SectionLabel className="mb-2">Assigned people</SectionLabel>
                <div className="max-h-40 overflow-y-auto space-y-1.5 rounded-md border border-white/10 p-2">
                  {workspaceMembers.length === 0 ? (
                    <p className="text-xs text-zinc-600 px-1">No workspace members to assign.</p>
                  ) : workspaceMembers.map((m) => {
                    const checked = draft.assigned_user_ids.includes(m.user_id);
                    return (
                      <label key={m.user_id} className="flex items-center gap-2 text-sm text-zinc-300 px-1 py-1 cursor-pointer hover:bg-white/[0.03] rounded">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleAssignee(m.user_id)}
                          data-testid={`stage-assign-${m.user_id}`}
                        />
                        <span className="truncate">{m.name || m.email}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
              <label className="block text-xs text-zinc-500">Notes
                <textarea
                  data-testid="stage-notes-input"
                  value={draft.notes}
                  onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                  rows={3}
                  className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 resize-y"
                />
              </label>
            </div>
            <div className="mt-5 flex items-center gap-2">
              <button
                type="button"
                data-testid="save-stage-btn"
                disabled={busy}
                onClick={saveStage}
                className="flex-1 rounded-md bg-gold text-black font-medium py-2.5 text-sm hover:bg-gold-hover disabled:opacity-60"
              >
                {busy ? "Saving…" : "Save changes"}
              </button>
              {canStructure && (
                <button
                  type="button"
                  data-testid="delete-stage-btn"
                  disabled={busy}
                  onClick={() => deleteStage(selected)}
                  className="rounded-md border border-rose-500/40 text-rose-400 p-2.5 hover:bg-rose-500/10 disabled:opacity-60"
                  title="Delete stage"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </GlassCard>
        </div>
      )}

      {adding && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setAdding(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="add-stage-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-white font-light">Add stage</h3>
              <button type="button" onClick={() => setAdding(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <label className="block text-xs text-zinc-500">Name
              <input
                data-testid="new-stage-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Cut & prep"
                className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2"
              />
            </label>
            <button
              type="button"
              data-testid="submit-new-stage"
              disabled={busy}
              onClick={createStage}
              className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm hover:bg-gold-hover disabled:opacity-60"
            >
              {busy ? "Adding…" : "Add to chain"}
            </button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
