import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, X, Wrench } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  reported: { label: "Reported", className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30" },
  diagnosed: { label: "Diagnosed", className: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  in_repair: { label: "In repair", className: "bg-amber-500/15 text-amber-200 border-amber-500/30" },
  resolved: { label: "Resolved", className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
};

const PRIORITY_META = {
  high: { label: "High", className: "text-rose-300" },
  medium: { label: "Medium", className: "text-amber-200" },
  low: { label: "Low", className: "text-zinc-400" },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.reported;
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide border", meta.className)}>
      {meta.label}
    </span>
  );
}

function personLabel(p) {
  if (!p) return "—";
  return p.name || p.email || "Teammate";
}

export default function Maintenance() {
  const { data, loading, error, reload } = useFetch("/maintenance/tickets");
  const { data: membersData } = useFetch("/members");
  const [showResolved, setShowResolved] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    equipment_name: "",
    description: "",
    priority: "medium",
    notes: "",
    assigned_technician: "",
  });

  const allTickets = data?.tickets || [];
  const visible = useMemo(
    () => (showResolved ? allTickets : allTickets.filter((t) => t.status !== "resolved")),
    [allTickets, showResolved],
  );
  const selected = allTickets.find((t) => t.id === selectedId) || null;
  const workspaceMembers = (membersData?.members || []).filter((m) => m.user_id && m.status === "active");

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      return;
    }
    setDraft({
      equipment_name: selected.equipment_name || "",
      description: selected.description || "",
      priority: selected.priority || "medium",
      notes: selected.notes || "",
      status: selected.status || "reported",
      assigned_technician: selected.assigned_technician || "",
    });
  }, [selectedId, selected?.updated_at]);

  if (loading) return <LoadingScreen label="Loading maintenance tickets" />;
  if (error) {
    const status = error?.response?.status;
    if (status === 403) {
      return (
        <ErrorScreen
          label="Access denied"
          message="You are not a member of Engineering & Maintenance. Ask your CEO to add you."
          onRetry={reload}
        />
      );
    }
    if (status === 404) {
      return (
        <ErrorScreen
          label="Department not enabled"
          message="Enable Engineering & Maintenance under Settings → Departments first."
          onRetry={reload}
        />
      );
    }
    return (
      <ErrorScreen
        label="Could not load tickets"
        message={fetchErrorMessage(error, "Maintenance data is unavailable.")}
        onRetry={reload}
      />
    );
  }

  const isLead = Boolean(data?.is_lead || data?.can_assign);
  const myId = data?.my_user_id;
  const isTech = selected && selected.assigned_technician === myId;
  const canEdit = Boolean(selected && (isLead || isTech));

  const createTicket = async () => {
    if (!form.equipment_name.trim()) {
      toast.error("Equipment name is required");
      return;
    }
    setBusy(true);
    try {
      const body = {
        equipment_name: form.equipment_name.trim(),
        description: form.description.trim(),
        priority: form.priority,
        notes: form.notes.trim(),
      };
      if (isLead && form.assigned_technician) {
        body.assigned_technician = form.assigned_technician;
      }
      const { data: res } = await api.post("/maintenance/tickets", body);
      toast.success("Ticket reported");
      setForm({ equipment_name: "", description: "", priority: "medium", notes: "", assigned_technician: "" });
      setAdding(false);
      await reload();
      if (res?.ticket?.id) setSelectedId(res.ticket.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create ticket");
    } finally {
      setBusy(false);
    }
  };

  const saveTicket = async () => {
    if (!selected || !draft) return;
    const body = {
      equipment_name: draft.equipment_name.trim(),
      description: draft.description,
      priority: draft.priority,
      notes: draft.notes,
      status: draft.status,
    };
    if (isLead) {
      body.assigned_technician = draft.assigned_technician || null;
    }
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/maintenance/tickets/${selected.id}`, body);
      toast.success("Ticket updated");
      await reload();
      if (res?.ticket?.id) setSelectedId(res.ticket.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update ticket");
    } finally {
      setBusy(false);
    }
  };

  const deleteTicket = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete ticket for “${selected.equipment_name}”?`)) return;
    setBusy(true);
    try {
      await api.delete(`/maintenance/tickets/${selected.id}`);
      toast.success("Ticket deleted");
      setSelectedId(null);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="maintenance-page">
      <PageHeader
        title={data?.name || "Engineering & Maintenance"}
        subtitle="Ticket queue — repairs and maintenance moving independently."
        action={(
          <button
            type="button"
            data-testid="add-maintenance-ticket-btn"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover"
          >
            <Plus className="w-4 h-4" /> Report ticket
          </button>
        )}
      />

      <div className="flex items-center justify-between gap-3 mb-4">
        <p className="text-xs text-zinc-500 font-mono">
          {visible.length} shown · {allTickets.length} total · open high-priority first
        </p>
        <label className="inline-flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            data-testid="maintenance-show-resolved"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="rounded border-white/20 bg-transparent"
          />
          Show resolved
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Wrench}
          title={allTickets.length ? "No open tickets" : "No tickets yet"}
          body={
            allTickets.length
              ? "Turn on “Show resolved” to see closed tickets, or report a new one."
              : "Report equipment issues to start the maintenance queue."
          }
          action={(
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"
            >
              <Plus className="w-4 h-4" /> Report ticket
            </button>
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-white/10 mb-6">
          <table className="w-full text-left text-sm" data-testid="maintenance-table">
            <thead>
              <tr className="border-b border-white/10 text-[10px] font-mono uppercase tracking-wide text-zinc-500">
                <th className="px-3 py-2 font-medium">Equipment</th>
                <th className="px-3 py-2 font-medium">Priority</th>
                <th className="px-3 py-2 font-medium">Technician</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => (
                <tr
                  key={t.id}
                  data-testid={`maintenance-row-${t.id}`}
                  onClick={() => setSelectedId(t.id)}
                  className={cn(
                    "border-b border-white/5 cursor-pointer transition-colors hover:bg-white/[0.03]",
                    selectedId === t.id && "bg-gold/[0.06]",
                  )}
                >
                  <td className="px-3 py-2.5 text-white truncate max-w-[16rem]">{t.equipment_name}</td>
                  <td className={cn("px-3 py-2.5 text-xs font-mono uppercase", PRIORITY_META[t.priority]?.className)}>
                    {PRIORITY_META[t.priority]?.label || t.priority}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-400 truncate max-w-[10rem]">
                    {personLabel(t.technician)}
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge status={t.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && draft && (
        <GlassCard className="p-5 space-y-4" data-testid="maintenance-detail">
          <div className="flex items-start justify-between gap-3">
            <div>
              <SectionLabel>Ticket detail</SectionLabel>
              <p className="text-white text-sm mt-1">{selected.equipment_name}</p>
            </div>
            <button type="button" onClick={() => setSelectedId(null)} className="text-zinc-500 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Equipment</span>
              <input
                data-testid="maintenance-edit-equipment"
                disabled={!canEdit || busy}
                value={draft.equipment_name}
                onChange={(e) => setDraft((d) => ({ ...d, equipment_name: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Priority</span>
              <select
                data-testid="maintenance-edit-priority"
                disabled={!canEdit || busy}
                value={draft.priority}
                onChange={(e) => setDraft((d) => ({ ...d, priority: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                {(data?.priorities || ["low", "medium", "high"]).map((p) => (
                  <option key={p} value={p}>{PRIORITY_META[p]?.label || p}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Status</span>
              <select
                data-testid="maintenance-edit-status"
                disabled={!canEdit || busy}
                value={draft.status}
                onChange={(e) => setDraft((d) => ({ ...d, status: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                {(data?.statuses || Object.keys(STATUS_META)).map((s) => (
                  <option key={s} value={s}>{STATUS_META[s]?.label || s}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Technician</span>
              <select
                data-testid="maintenance-edit-tech"
                disabled={!isLead || busy}
                value={draft.assigned_technician || ""}
                onChange={(e) => setDraft((d) => ({ ...d, assigned_technician: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                <option value="">Unassigned</option>
                {workspaceMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
                ))}
              </select>
              {!isLead && (
                <span className="text-[10px] text-zinc-600">Only a lead or CEO can assign a technician</span>
              )}
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Description</span>
            <textarea
              data-testid="maintenance-edit-description"
              disabled={!canEdit || busy}
              value={draft.description}
              onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
              rows={2}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Notes</span>
            <textarea
              data-testid="maintenance-edit-notes"
              disabled={!canEdit || busy}
              value={draft.notes}
              onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
              rows={3}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
            />
          </label>

          <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
            <span>Reported by: <span className="text-zinc-300">{personLabel(selected.reporter)}</span></span>
            <span>Status: <StatusBadge status={selected.status} /></span>
          </div>

          <div className="flex flex-wrap gap-2">
            {canEdit && (
              <button
                type="button"
                disabled={busy}
                data-testid="maintenance-save-btn"
                onClick={saveTicket}
                className="rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
              >
                Save changes
              </button>
            )}
            {isLead && (
              <button
                type="button"
                disabled={busy}
                data-testid="maintenance-delete-btn"
                onClick={deleteTicket}
                className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/30 text-rose-300 text-sm px-3 py-2 hover:bg-rose-500/10 disabled:opacity-50 ml-auto"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            )}
          </div>
        </GlassCard>
      )}

      {adding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70" onClick={() => !busy && setAdding(false)} />
          <div className="relative w-full max-w-md rounded-md border border-white/10 bg-[#141417] p-5 space-y-3" data-testid="maintenance-create-modal">
            <div className="flex items-center justify-between">
              <p className="text-sm text-white font-medium">Report maintenance ticket</p>
              <button type="button" onClick={() => setAdding(false)} className="text-zinc-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Equipment</span>
              <input
                data-testid="maintenance-new-equipment"
                value={form.equipment_name}
                onChange={(e) => setForm((f) => ({ ...f, equipment_name: e.target.value }))}
                placeholder="CNC Mill #3"
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                autoFocus
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Priority</span>
              <select
                data-testid="maintenance-new-priority"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              >
                {(data?.priorities || ["low", "medium", "high"]).map((p) => (
                  <option key={p} value={p}>{PRIORITY_META[p]?.label || p}</option>
                ))}
              </select>
            </label>
            {isLead && (
              <label className="block space-y-1">
                <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Technician (optional)</span>
                <select
                  data-testid="maintenance-new-tech"
                  value={form.assigned_technician}
                  onChange={(e) => setForm((f) => ({ ...f, assigned_technician: e.target.value }))}
                  className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                >
                  <option value="">Unassigned</option>
                  {workspaceMembers.map((m) => (
                    <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Description</span>
              <textarea
                data-testid="maintenance-new-description"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Notes</span>
              <textarea
                data-testid="maintenance-new-notes"
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              />
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setAdding(false)} className="text-sm text-zinc-400 px-3 py-2">Cancel</button>
              <button
                type="button"
                disabled={busy}
                data-testid="maintenance-create-submit"
                onClick={createTicket}
                className="rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
              >
                Submit ticket
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
