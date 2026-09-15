import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, X, Factory, Trash2 } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState, ConfirmDialog,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  awaiting_materials: {
    label: "Awaiting materials",
    className: "bg-helm-status-warning/12 text-helm-fg border-helm-status-warning/35",
  },
  in_production: {
    label: "In production",
    className: "bg-helm-muted/12 text-helm-fg border-helm-muted/35",
  },
  quality_check: {
    label: "Quality check",
    className: "bg-helm-muted/12 text-helm-fg border-helm-muted/35",
  },
  completed: {
    label: "Completed",
    className: "bg-helm-status-positive/12 text-helm-fg border-helm-status-positive/35",
  },
};

const STATUS_ORDER = ["awaiting_materials", "in_production", "quality_check", "completed"];
const CLOSED = new Set(["completed"]);

const CATEGORY_LABELS = {
  material: "Material",
  labor: "Labor",
  machine: "Machine",
  quality: "Quality",
  other: "Other",
};

const PROC_STATUS_LABELS = {
  requested: "Requested",
  approved: "Approved",
  ordered: "Ordered",
  delivered: "Delivered",
  rejected: "Rejected",
};

const MAINT_STATUS_LABELS = {
  reported: "Reported",
  diagnosed: "Diagnosed",
  in_repair: "In repair",
  resolved: "Resolved",
};

const PRIORITY_RANK = { high: 0, normal: 1, low: 2 };

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.in_production;
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide border", meta.className)}>
      {meta.label}
    </span>
  );
}

function isDueDateOverdue(dueDate, status) {
  if (CLOSED.has(status)) return false;
  const raw = (dueDate || "").trim();
  if (!raw) return false;
  const end = new Date(`${raw}T23:59:59`);
  if (Number.isNaN(end.getTime())) return false;
  return end.getTime() < Date.now();
}

function formatCycleTime(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return null;
  const s = Number(seconds);
  if (s >= 86400) {
    const days = s / 86400;
    return `${days >= 10 ? Math.round(days) : days.toFixed(1).replace(/\.0$/, "")}d`;
  }
  if (s >= 3600) {
    const hours = s / 3600;
    return `${hours >= 10 ? Math.round(hours) : hours.toFixed(1).replace(/\.0$/, "")}h`;
  }
  return `${Math.max(1, Math.round(s / 60))}m`;
}

function compareOrders(a, b) {
  const aClosed = CLOSED.has(a?.status);
  const bClosed = CLOSED.has(b?.status);
  if (aClosed !== bClosed) return aClosed ? 1 : -1;
  const pa = PRIORITY_RANK[a?.priority] ?? PRIORITY_RANK.normal;
  const pb = PRIORITY_RANK[b?.priority] ?? PRIORITY_RANK.normal;
  if (pa !== pb) return pa - pb;
  const da = (a?.due_date || "").trim();
  const db = (b?.due_date || "").trim();
  if (da && db && da !== db) return da < db ? -1 : 1;
  if (da && !db) return -1;
  if (!da && db) return 1;
  return String(a?.reference || "").localeCompare(String(b?.reference || ""));
}

const emptyForm = () => ({
  reference: "",
  product: "",
  quantity_planned: "",
  customer: "",
  priority: "normal",
  due_date: "",
  linked_procurement_request_id: "",
  linked_maintenance_ticket_id: "",
  notes: "",
});

export default function Production() {
  const { data, loading, error, reload } = useFetch("/production/work-orders");
  const { data: membersData } = useFetch("/members");
  const [showClosed, setShowClosed] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [completing, setCompleting] = useState(false);
  const [completeQty, setCompleteQty] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const allOrders = useMemo(
    () => [...(data?.work_orders || [])].sort(compareOrders),
    [data?.work_orders],
  );
  const visible = useMemo(
    () => (showClosed ? allOrders : allOrders.filter((o) => !CLOSED.has(o.status))),
    [allOrders, showClosed],
  );
  const selected = useMemo(
    () => allOrders.find((o) => o.id === selectedId) || null,
    [allOrders, selectedId],
  );
  const openProcurement = data?.open_procurement_requests || [];
  const openMaintenance = data?.open_maintenance_tickets || [];
  const priorities = data?.priorities || ["low", "normal", "high"];
  const blockedCategories = data?.blocked_categories || Object.keys(CATEGORY_LABELS);
  const statuses = data?.statuses || STATUS_ORDER;
  const workspaceMembers = (membersData?.members || []).filter(
    (m) => m.user_id && m.status === "active",
  );
  const cycleLabel = formatCycleTime(data?.average_cycle_time?.average_seconds);

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      setCompleting(false);
      return;
    }
    setDraft({
      reference: selected.reference || "",
      product: selected.product || "",
      quantity_planned: selected.quantity_planned == null ? "" : String(selected.quantity_planned),
      quantity_produced: selected.quantity_produced == null ? "" : String(selected.quantity_produced),
      customer: selected.customer || "",
      priority: selected.priority || "normal",
      due_date: selected.due_date || "",
      status: selected.status || "in_production",
      blocked: Boolean(selected.blocked),
      blocked_category: selected.blocked_reason?.category || "",
      blocked_detail: selected.blocked_reason?.detail || "",
      linked_procurement_request_id: selected.linked_procurement_request_id || "",
      linked_maintenance_ticket_id: selected.linked_maintenance_ticket_id || "",
      assigned_user_ids: [...(selected.assigned_user_ids || [])],
      notes: selected.notes || "",
    });
    setCompleting(false);
  }, [selected]);

  if (loading) return <LoadingScreen label="Loading production" />;
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

  const createOrder = async () => {
    if (!form.reference.trim()) {
      toast.error("Reference is required");
      return;
    }
    const body = {
      reference: form.reference.trim(),
      product: form.product.trim(),
      customer: form.customer.trim(),
      priority: form.priority || "normal",
      due_date: form.due_date.trim(),
      notes: form.notes.trim(),
      linked_procurement_request_id: form.linked_procurement_request_id || null,
      linked_maintenance_ticket_id: form.linked_maintenance_ticket_id || null,
    };
    if (form.quantity_planned !== "") {
      const q = Number(form.quantity_planned);
      if (!Number.isFinite(q)) {
        toast.error("Quantity planned must be a number");
        return;
      }
      body.quantity_planned = q;
    }
    setBusy(true);
    try {
      const { data: res } = await api.post("/production/work-orders", body);
      toast.success("Work order created");
      setForm(emptyForm());
      setAdding(false);
      await reload();
      if (res?.work_order?.id) setSelectedId(res.work_order.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create work order");
    } finally {
      setBusy(false);
    }
  };

  const saveOrder = async (overrides = {}) => {
    if (!selected || !draft) return;
    const body = { ...overrides };
    body.reference = draft.reference.trim();
    body.product = draft.product.trim();
    body.customer = draft.customer.trim();
    body.priority = draft.priority;
    body.due_date = draft.due_date.trim();
    body.notes = draft.notes;
    body.assigned_user_ids = draft.assigned_user_ids;
    body.linked_procurement_request_id = draft.linked_procurement_request_id || "";
    body.linked_maintenance_ticket_id = draft.linked_maintenance_ticket_id || "";
    body.blocked = Boolean(draft.blocked);
    if (draft.blocked) {
      body.blocked_reason = {
        category: draft.blocked_category,
        detail: draft.blocked_detail,
      };
    } else {
      body.blocked_reason = null;
    }
    if (draft.quantity_planned === "") body.quantity_planned = null;
    else {
      const q = Number(draft.quantity_planned);
      if (!Number.isFinite(q)) {
        toast.error("Quantity planned must be a number");
        return;
      }
      body.quantity_planned = q;
    }
    if (draft.quantity_produced !== "" && draft.quantity_produced != null) {
      const q = Number(draft.quantity_produced);
      if (!Number.isFinite(q)) {
        toast.error("Quantity produced must be a number");
        return;
      }
      body.quantity_produced = q;
    }
    if (!("status" in body)) body.status = draft.status;

    setBusy(true);
    try {
      const { data: res } = await api.patch(`/production/work-orders/${selected.id}`, body);
      toast.success("Work order updated");
      await reload();
      if (res?.work_order?.id) setSelectedId(res.work_order.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update work order");
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (status) => {
    if (status === "completed") {
      const planned = selected?.quantity_planned;
      setCompleteQty(planned == null ? "" : String(planned));
      setCompleting(true);
      return;
    }
    await saveOrder({ status });
  };

  const confirmComplete = async () => {
    const q = Number(completeQty);
    if (!Number.isFinite(q)) {
      toast.error("Enter quantity produced");
      return;
    }
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/production/work-orders/${selected.id}`, {
        status: "completed",
        quantity_produced: q,
      });
      toast.success("Work order completed");
      setCompleting(false);
      await reload();
      if (res?.work_order?.id) setSelectedId(res.work_order.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not complete");
    } finally {
      setBusy(false);
    }
  };

  const deleteOrder = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await api.delete(`/production/work-orders/${selected.id}`);
      toast.success("Work order deleted");
      setConfirmDelete(false);
      setSelectedId(null);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
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

  const action = (
    <button
      type="button"
      data-testid="add-work-order-btn"
      onClick={() => setAdding(true)}
      className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
    >
      <Plus className="w-4 h-4" /> New work order
    </button>
  );

  return (
    <div data-testid="production-page">
      <PageHeader
        title={data?.name || "Production"}
        subtitle="Work order queue — fixed statuses, no pipeline setup."
        action={action}
      />

      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <p className="text-xs text-helm-muted font-mono">
          {visible.length} shown · {allOrders.length} total
          {cycleLabel && data?.average_cycle_time?.sample_count ? (
            <span data-testid="average-cycle-time">
              {" "}· avg cycle {cycleLabel} ({data.average_cycle_time.sample_count} done)
            </span>
          ) : null}
        </p>
        <label className="inline-flex items-center gap-2 text-xs text-helm-muted cursor-pointer select-none">
          <input
            type="checkbox"
            data-testid="production-show-completed"
            checked={showClosed}
            onChange={(e) => setShowClosed(e.target.checked)}
            className="rounded border-helm-fg/20 bg-transparent"
          />
          Show completed
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Factory}
          title={allOrders.length ? "No open work orders" : "No work orders yet"}
          body={
            allOrders.length
              ? "Turn on “Show completed” to see finished jobs, or create a new work order."
              : "Create a work order to start the queue — no stage setup needed."
          }
          action={(
            <button
              type="button"
              data-testid="add-work-order-empty"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2 hover:bg-helm-gold-hover"
            >
              <Plus className="w-4 h-4" /> New work order
            </button>
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-helm-line mb-6">
          <table className="w-full text-left text-sm" data-testid="production-table">
            <thead>
              <tr className="border-b border-helm-line text-[10px] font-mono uppercase tracking-wide text-helm-muted">
                <th className="px-3 py-2 font-medium">Reference</th>
                <th className="px-3 py-2 font-medium">Product</th>
                <th className="px-3 py-2 font-medium">Customer</th>
                <th className="px-3 py-2 font-medium">Priority</th>
                <th className="px-3 py-2 font-medium">Due</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((order) => {
                const overdue = isDueDateOverdue(order.due_date, order.status);
                return (
                  <tr
                    key={order.id}
                    data-testid={`production-row-${order.id}`}
                    onClick={() => setSelectedId(order.id)}
                    className={cn(
                      "border-b border-helm-line cursor-pointer transition-colors hover:bg-helm-fg/[0.03]",
                      selectedId === order.id && "bg-helm-gold/12",
                    )}
                  >
                    <td className="px-3 py-2.5 text-helm-fg">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="truncate max-w-[12rem] font-medium">{order.reference}</span>
                        {order.blocked && (
                          <span
                            data-testid={`blocked-badge-${order.id}`}
                            className="shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide border border-helm-status-negative/35 bg-helm-status-negative/12 text-helm-status-negative"
                            title={order.blocked_reason?.detail || ""}
                          >
                            Blocked
                            {order.blocked_reason?.category
                              ? ` · ${CATEGORY_LABELS[order.blocked_reason.category] || order.blocked_reason.category}`
                              : ""}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-helm-muted truncate max-w-[10rem]">
                      {[
                        order.product || null,
                        order.quantity_planned != null ? `× ${order.quantity_planned}` : null,
                        order.status === "completed" && order.quantity_produced != null
                          ? `(made ${order.quantity_produced})`
                          : null,
                      ].filter(Boolean).join(" ") || "—"}
                    </td>
                    <td className="px-3 py-2.5 text-helm-muted truncate max-w-[8rem]">{order.customer || "—"}</td>
                    <td className="px-3 py-2.5 text-helm-muted capitalize">{order.priority || "normal"}</td>
                    <td className={cn("px-3 py-2.5 font-mono text-xs", overdue ? "text-helm-status-negative" : "text-helm-muted")}>
                      {order.due_date ? (overdue ? `Overdue ${order.due_date}` : order.due_date) : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-col gap-1">
                        <StatusBadge status={order.status} />
                        {order.linked_procurement && (
                          <span className="text-[10px] text-helm-muted truncate max-w-[9rem]" data-testid={`linked-proc-${order.id}`}>
                            Proc: {order.linked_procurement.item || order.linked_procurement.id}
                            {" · "}
                            {PROC_STATUS_LABELS[order.linked_procurement.status] || order.linked_procurement.status}
                          </span>
                        )}
                        {order.linked_maintenance && (
                          <span className="text-[10px] text-helm-muted truncate max-w-[9rem]" data-testid={`linked-maint-${order.id}`}>
                            Maint: {order.linked_maintenance.equipment_name || order.linked_maintenance.id}
                            {" · "}
                            {MAINT_STATUS_LABELS[order.linked_maintenance.status] || order.linked_maintenance.status}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && draft && (
        <GlassCard className="p-5 space-y-4" data-testid="work-order-detail">
          <div className="flex items-start justify-between gap-3">
            <div>
              <SectionLabel>Work order</SectionLabel>
              <p className="text-helm-fg text-sm mt-1">{selected.reference}</p>
            </div>
            <button type="button" onClick={() => setSelectedId(null)} className="text-helm-muted hover:text-helm-fg">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Reference</span>
              <input
                data-testid="wo-reference-input"
                disabled={busy}
                value={draft.reference}
                onChange={(e) => setDraft((d) => ({ ...d, reference: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Product</span>
              <input
                data-testid="wo-product-input"
                disabled={busy}
                value={draft.product}
                onChange={(e) => setDraft((d) => ({ ...d, product: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Qty planned</span>
              <input
                data-testid="wo-qty-planned"
                disabled={busy}
                value={draft.quantity_planned}
                onChange={(e) => setDraft((d) => ({ ...d, quantity_planned: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Qty produced</span>
              <input
                data-testid="wo-qty-produced"
                disabled={busy || draft.status !== "completed"}
                value={draft.quantity_produced}
                onChange={(e) => setDraft((d) => ({ ...d, quantity_produced: e.target.value }))}
                placeholder={draft.status === "completed" ? "Required" : "Set on complete"}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Customer</span>
              <input
                data-testid="wo-customer-input"
                disabled={busy}
                value={draft.customer}
                onChange={(e) => setDraft((d) => ({ ...d, customer: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Priority</span>
              <select
                data-testid="wo-priority-select"
                disabled={busy}
                value={draft.priority}
                onChange={(e) => setDraft((d) => ({ ...d, priority: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              >
                {priorities.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Due date</span>
              <input
                data-testid="wo-due-date-input"
                type="date"
                disabled={busy}
                value={draft.due_date}
                onChange={(e) => setDraft((d) => ({ ...d, due_date: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Linked procurement</span>
              <select
                data-testid="wo-linked-procurement"
                disabled={busy}
                value={draft.linked_procurement_request_id}
                onChange={(e) => setDraft((d) => ({ ...d, linked_procurement_request_id: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              >
                <option value="">None</option>
                {openProcurement.map((r) => (
                  <option key={r.id} value={r.id}>
                    {(r.item || r.id)} · {PROC_STATUS_LABELS[r.status] || r.status}
                  </option>
                ))}
                {draft.linked_procurement_request_id
                  && !openProcurement.some((r) => r.id === draft.linked_procurement_request_id)
                  && selected.linked_procurement && (
                    <option value={draft.linked_procurement_request_id}>
                      {selected.linked_procurement.item || draft.linked_procurement_request_id}
                      {" · "}
                      {PROC_STATUS_LABELS[selected.linked_procurement.status] || selected.linked_procurement.status}
                    </option>
                )}
              </select>
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Notes</span>
            <textarea
              data-testid="wo-notes-input"
              disabled={busy}
              value={draft.notes}
              onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
              rows={3}
              className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
            />
          </label>

          <div className="space-y-2">
            <label className="inline-flex items-center gap-2 text-sm text-helm-fg cursor-pointer">
              <input
                type="checkbox"
                data-testid="wo-blocked-toggle"
                checked={draft.blocked}
                disabled={busy}
                onChange={(e) => setDraft((d) => ({ ...d, blocked: e.target.checked }))}
              />
              Blocked
            </label>
            {draft.blocked && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Reason</span>
                  <select
                    data-testid="wo-blocked-category"
                    disabled={busy}
                    value={draft.blocked_category}
                    onChange={(e) => setDraft((d) => ({ ...d, blocked_category: e.target.value }))}
                    className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                  >
                    <option value="">Select…</option>
                    {blockedCategories.map((c) => (
                      <option key={c} value={c}>{CATEGORY_LABELS[c] || c}</option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Detail</span>
                  <input
                    data-testid="wo-blocked-detail"
                    disabled={busy}
                    value={draft.blocked_detail}
                    onChange={(e) => setDraft((d) => ({ ...d, blocked_detail: e.target.value }))}
                    className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                  />
                </label>
                {(draft.blocked_category === "machine" || draft.linked_maintenance_ticket_id) && (
                  <label className="space-y-1 md:col-span-2">
                    <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Linked maintenance ticket</span>
                    <select
                      data-testid="wo-linked-maintenance"
                      disabled={busy}
                      value={draft.linked_maintenance_ticket_id}
                      onChange={(e) => setDraft((d) => ({ ...d, linked_maintenance_ticket_id: e.target.value }))}
                      className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
                    >
                      <option value="">None</option>
                      {openMaintenance.map((t) => (
                        <option key={t.id} value={t.id}>
                          {(t.equipment_name || t.id)} · {MAINT_STATUS_LABELS[t.status] || t.status}
                        </option>
                      ))}
                      {draft.linked_maintenance_ticket_id
                        && !openMaintenance.some((t) => t.id === draft.linked_maintenance_ticket_id)
                        && selected.linked_maintenance && (
                          <option value={draft.linked_maintenance_ticket_id}>
                            {selected.linked_maintenance.equipment_name || draft.linked_maintenance_ticket_id}
                            {" · "}
                            {MAINT_STATUS_LABELS[selected.linked_maintenance.status] || selected.linked_maintenance.status}
                          </option>
                      )}
                    </select>
                  </label>
                )}
              </div>
            )}
          </div>

          <div>
            <SectionLabel className="mb-2">Assignees</SectionLabel>
            <div className="max-h-32 overflow-y-auto space-y-1.5 rounded-md border border-helm-line p-2">
              {workspaceMembers.length === 0 ? (
                <p className="text-xs text-helm-muted px-1">No workspace members to assign.</p>
              ) : workspaceMembers.map((m) => {
                const checked = draft.assigned_user_ids.includes(m.user_id);
                return (
                  <label key={m.user_id} className="flex items-center gap-2 text-sm text-helm-fg px-1 py-1 cursor-pointer hover:bg-helm-fg/[0.03] rounded">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleAssignee(m.user_id)}
                      data-testid={`wo-assign-${m.user_id}`}
                    />
                    <span className="truncate">{m.name || m.email}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted mr-1">Move to</span>
            {STATUS_ORDER.filter((s) => statuses.includes(s)).map((st) => (
              <button
                key={st}
                type="button"
                disabled={busy || draft.status === st}
                data-testid={`wo-status-${st}`}
                onClick={() => setStatus(st)}
                className={cn(
                  "rounded-md border text-xs px-2.5 py-1.5 disabled:opacity-40",
                  draft.status === st
                    ? "border-helm-gold/35 bg-helm-gold/12 text-helm-gold"
                    : "border-helm-line text-helm-fg hover:border-helm-gold/35",
                )}
              >
                {STATUS_META[st]?.label || st}
              </button>
            ))}
          </div>

          {completing && (
            <div className="rounded-md border border-helm-line bg-helm-fg/[0.02] p-3 space-y-2" data-testid="complete-prompt">
              <p className="text-sm text-helm-fg">Quantity produced</p>
              <input
                data-testid="complete-qty-input"
                value={completeQty}
                onChange={(e) => setCompleteQty(e.target.value)}
                className="w-full max-w-xs rounded-md border border-helm-line bg-helm-card px-3 py-2 text-sm text-helm-fg"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  data-testid="confirm-complete-btn"
                  onClick={confirmComplete}
                  className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover disabled:opacity-50"
                >
                  Complete
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setCompleting(false)}
                  className="rounded-md border border-helm-line text-sm px-3 py-2 text-helm-fg"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              data-testid="save-work-order-btn"
              onClick={() => saveOrder()}
              className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover disabled:opacity-50"
            >
              Save changes
            </button>
            <StatusBadge status={selected.status} />
            <button
              type="button"
              disabled={busy}
              data-testid="delete-work-order-btn"
              onClick={() => setConfirmDelete(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-helm-status-negative/35 text-helm-status-negative text-sm px-3 py-2 hover:bg-helm-status-negative/10 disabled:opacity-50 ml-auto"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </div>
        </GlassCard>
      )}

      <ConfirmDialog
        open={confirmDelete && Boolean(selected)}
        title={`Delete work order “${selected?.reference || ""}”?`}
        description="This permanently removes the work order from the queue. This can’t be undone."
        confirmLabel="Delete work order"
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={deleteOrder}
        testId="delete-work-order-confirm"
      />

      {adding && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => setAdding(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="add-work-order-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-helm-fg font-light">New work order</h3>
              <button type="button" onClick={() => setAdding(false)} className="text-helm-muted hover:text-helm-fg"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <label className="block text-xs text-helm-muted">Reference
                <input
                  data-testid="new-wo-reference"
                  value={form.reference}
                  onChange={(e) => setForm((o) => ({ ...o, reference: e.target.value }))}
                  placeholder="Order #245"
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-helm-muted">Product
                  <input
                    data-testid="new-wo-product"
                    value={form.product}
                    onChange={(e) => setForm((o) => ({ ...o, product: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
                <label className="block text-xs text-helm-muted">Qty planned
                  <input
                    data-testid="new-wo-qty-planned"
                    type="number"
                    value={form.quantity_planned}
                    onChange={(e) => setForm((o) => ({ ...o, quantity_planned: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
              </div>
              <label className="block text-xs text-helm-muted">Customer
                <input
                  data-testid="new-wo-customer"
                  value={form.customer}
                  onChange={(e) => setForm((o) => ({ ...o, customer: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-helm-muted">Priority
                  <select
                    data-testid="new-wo-priority"
                    value={form.priority}
                    onChange={(e) => setForm((o) => ({ ...o, priority: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  >
                    {priorities.map((p) => (
                      <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs text-helm-muted">Due date
                  <input
                    data-testid="new-wo-due-date"
                    type="date"
                    value={form.due_date}
                    onChange={(e) => setForm((o) => ({ ...o, due_date: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
              </div>
              <label className="block text-xs text-helm-muted">Link open procurement (optional)
                <select
                  data-testid="new-wo-linked-procurement"
                  value={form.linked_procurement_request_id}
                  onChange={(e) => setForm((o) => ({ ...o, linked_procurement_request_id: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                >
                  <option value="">None</option>
                  {openProcurement.map((r) => (
                    <option key={r.id} value={r.id}>
                      {(r.item || r.id)} · {PROC_STATUS_LABELS[r.status] || r.status}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button
              type="button"
              data-testid="submit-new-work-order"
              disabled={busy}
              onClick={createOrder}
              className="mt-5 w-full rounded-md bg-helm-gold text-helm-navy font-medium py-2.5 text-sm hover:bg-helm-gold-hover disabled:opacity-60"
            >
              {busy ? "Creating…" : "Create work order"}
            </button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
