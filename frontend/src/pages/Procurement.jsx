import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, X, Package } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState, ConfirmDialog,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  requested: { label: "Requested", className: "bg-helm-muted/15 text-helm-fg border-helm-muted/30" },
  approved: { label: "Approved", className: "bg-helm-muted/15 text-helm-muted border-helm-muted/30" },
  ordered: { label: "Ordered", className: "bg-helm-status-warning/15 text-helm-status-warning border-helm-status-warning/30" },
  delivered: { label: "Delivered", className: "bg-helm-status-positive/15 text-helm-status-positive border-helm-status-positive/30" },
  rejected: { label: "Rejected", className: "bg-helm-status-negative/15 text-helm-status-negative border-helm-status-negative/30" },
};

const CLOSED = new Set(["delivered", "rejected"]);

function isExpectedDeliveryOverdue(dateStr, status) {
  if (CLOSED.has(status)) return false;
  const raw = (dateStr || "").trim();
  if (!raw) return false;
  const end = new Date(`${raw}T23:59:59`);
  if (Number.isNaN(end.getTime())) return false;
  return end.getTime() < Date.now();
}

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.requested;
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

function formatBlockingOrders(orders) {
  if (!orders?.length) return "";
  return orders.map((o) => {
    const ref = o.reference || o.work_order_id || "work order";
    const due = o.due_date || "";
    return due ? `${ref} (due ${due})` : ref;
  }).join(", ");
}

function BlockingProductionBadge({ orders, requestId }) {
  if (!orders?.length) return null;
  const label = formatBlockingOrders(orders);
  return (
    <span
      data-testid={`blocking-production-badge-${requestId}`}
      title={label}
      className="inline-flex max-w-full items-center truncate rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide border border-helm-gold/40 bg-helm-gold/10 text-helm-gold"
    >
      Blocking: {label}
    </span>
  );
}

export default function Procurement() {
  const { data, loading, error, reload } = useFetch("/procurement/requests");
  const [showClosed, setShowClosed] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [orderDatePrompt, setOrderDatePrompt] = useState(null);
  const [form, setForm] = useState({ item: "", quantity: "1", vendor_name: "", cost: "", notes: "", expected_delivery_date: "" });

  const allRequests = useMemo(() => data?.requests || [], [data?.requests]);
  const visible = useMemo(() => {
    const base = showClosed ? allRequests : allRequests.filter((r) => !CLOSED.has(r.status));
    // Blocking production impact always sorts first.
    return [...base].sort((a, b) => {
      const ab = (a.blocking_production_orders || []).length ? 0 : 1;
      const bb = (b.blocking_production_orders || []).length ? 0 : 1;
      return ab - bb;
    });
  }, [allRequests, showClosed]);
  const selected = useMemo(
    () => allRequests.find((r) => r.id === selectedId) || null,
    [allRequests, selectedId],
  );

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      return;
    }
    setDraft({
      item: selected.item || "",
      quantity: String(selected.quantity ?? 1),
      vendor_name: selected.vendor_name || "",
      cost: selected.cost == null ? "" : String(selected.cost),
      notes: selected.notes || "",
      expected_delivery_date: selected.expected_delivery_date || "",
      status: selected.status || "requested",
    });
  }, [selected]);

  if (loading) return <LoadingScreen label="Loading procurement" />;
  if (error) {
    const status = error?.response?.status;
    if (status === 403) {
      return (
        <ErrorScreen
          label="Access denied"
          message="You are not a member of Procurement. Ask your CEO to add you."
          onRetry={reload}
        />
      );
    }
    if (status === 404) {
      return (
        <ErrorScreen
          label="Procurement not enabled"
          message="Enable Procurement under Settings → Departments first."
          onRetry={reload}
        />
      );
    }
    return (
      <ErrorScreen
        label="Could not load Procurement"
        message={fetchErrorMessage(error, "Procurement data is unavailable.")}
        onRetry={reload}
      />
    );
  }

  const canApprove = Boolean(data?.can_approve);
  const myId = data?.my_user_id;
  const isOwner = selected && selected.requested_by === myId;
  const canEditContent = Boolean(
    selected && (canApprove || (isOwner && selected.status === "requested")),
  );
  const canDeleteSelected = Boolean(
    selected && (canApprove || (isOwner && selected.status === "requested")),
  );

  const createRequest = async () => {
    if (!form.item.trim()) {
      toast.error("Item is required");
      return;
    }
    const quantity = Number(form.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      toast.error("Quantity must be a positive number");
      return;
    }
    let cost = null;
    if (form.cost.trim() !== "") {
      cost = Number(form.cost);
      if (!Number.isFinite(cost) || cost < 0) {
        toast.error("Cost must be a non-negative number");
        return;
      }
    }
    setBusy(true);
    try {
      const { data: res } = await api.post("/procurement/requests", {
        item: form.item.trim(),
        quantity,
        vendor_name: form.vendor_name.trim(),
        cost,
        notes: form.notes.trim(),
        expected_delivery_date: form.expected_delivery_date.trim(),
      });
      toast.success("Request submitted");
      setForm({ item: "", quantity: "1", vendor_name: "", cost: "", notes: "", expected_delivery_date: "" });
      setAdding(false);
      await reload();
      if (res?.request?.id) setSelectedId(res.request.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create request");
    } finally {
      setBusy(false);
    }
  };

  const saveRequest = async (overrides = {}) => {
    if (!selected || !draft) return;
    const body = { ...overrides };
    if (canEditContent) {
      const quantity = Number(draft.quantity);
      if (!Number.isFinite(quantity) || quantity <= 0) {
        toast.error("Quantity must be a positive number");
        return;
      }
      body.item = draft.item.trim();
      body.quantity = quantity;
      body.vendor_name = draft.vendor_name.trim();
      body.notes = draft.notes;
      if (draft.cost.trim() === "") {
        // omit cost if cleared — leave existing unless lead clears via 0
      } else {
        const cost = Number(draft.cost);
        if (!Number.isFinite(cost) || cost < 0) {
          toast.error("Cost must be a non-negative number");
          return;
        }
        body.cost = cost;
      }
    }
    if (canEditContent || canApprove) {
      body.expected_delivery_date = (draft.expected_delivery_date || "").trim();
    }
    if (!Object.keys(body).length) return;
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/procurement/requests/${selected.id}`, body);
      toast.success("Request updated");
      await reload();
      if (res?.request?.id) setSelectedId(res.request.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update request");
    } finally {
      setBusy(false);
    }
  };

  const applyStatus = async (status, extra = {}) => {
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/procurement/requests/${selected.id}`, { status, ...extra });
      toast.success(`Marked ${STATUS_META[status]?.label || status}`);
      await reload();
      if (res?.request?.id) setSelectedId(res.request.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update status");
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (status) => {
    if (
      status === "ordered"
      && !(draft?.expected_delivery_date || selected?.expected_delivery_date || "").trim()
    ) {
      setOrderDatePrompt({ status, date: "" });
      return;
    }
    await applyStatus(status);
  };

  const confirmOrderDatePrompt = async ({ skip } = {}) => {
    if (!orderDatePrompt) return;
    const { status } = orderDatePrompt;
    const date = (orderDatePrompt.date || "").trim();
    setOrderDatePrompt(null);
    if (skip || !date) {
      await applyStatus(status);
      return;
    }
    setDraft((d) => (d ? { ...d, expected_delivery_date: date } : d));
    await applyStatus(status, { expected_delivery_date: date });
  };

  const deleteRequest = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await api.delete(`/procurement/requests/${selected.id}`);
      toast.success("Request deleted");
      setConfirmDelete(false);
      setSelectedId(null);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
    } finally {
      setBusy(false);
    }
  };

  const action = (
    <button
      type="button"
      data-testid="add-procurement-request-btn"
      onClick={() => setAdding(true)}
      className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
    >
      <Plus className="w-4 h-4" /> New request
    </button>
  );

  return (
    <div data-testid="procurement-page">
      <PageHeader
        title={data?.name || "Procurement"}
        subtitle="Purchase request queue — each request moves independently."
        action={action}
      />

      <div className="flex items-center justify-between gap-3 mb-4">
        <p className="text-xs text-helm-muted font-mono">
          {visible.length} shown · {allRequests.length} total
        </p>
        <label className="inline-flex items-center gap-2 text-xs text-helm-muted cursor-pointer select-none">
          <input
            type="checkbox"
            data-testid="procurement-show-closed"
            checked={showClosed}
            onChange={(e) => setShowClosed(e.target.checked)}
            className="rounded border-helm-fg/20 bg-transparent"
          />
          Show delivered &amp; rejected
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Package}
          title={allRequests.length ? "No open requests" : "No requests yet"}
          body={
            allRequests.length
              ? "Turn on “Show delivered & rejected” to see closed items, or submit a new request."
              : "Submit a purchase request to start the queue."
          }
          action={(
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2 hover:bg-helm-gold-hover"
            >
              <Plus className="w-4 h-4" /> New request
            </button>
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-helm-line mb-6">
          <table className="w-full text-left text-sm" data-testid="procurement-table">
            <thead>
              <tr className="border-b border-helm-line text-[10px] font-mono uppercase tracking-wide text-helm-muted">
                <th className="px-3 py-2 font-medium">Item</th>
                <th className="px-3 py-2 font-medium">Qty</th>
                <th className="px-3 py-2 font-medium">Vendor</th>
                <th className="px-3 py-2 font-medium">Requester</th>
                <th className="px-3 py-2 font-medium">Expected</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((req) => (
                <tr
                  key={req.id}
                  data-testid={`procurement-row-${req.id}`}
                  onClick={() => setSelectedId(req.id)}
                  className={cn(
                    "border-b border-helm-line cursor-pointer transition-colors hover:bg-helm-fg/[0.03]",
                    selectedId === req.id && "bg-helm-gold/[0.06]",
                  )}
                >
                  <td className="px-3 py-2.5 text-helm-fg max-w-[14rem]">
                    <div className="flex flex-col gap-1 min-w-0">
                      <span className="truncate">{req.item}</span>
                      <BlockingProductionBadge
                        orders={req.blocking_production_orders}
                        requestId={req.id}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-helm-fg font-mono text-xs">{req.quantity}</td>
                  <td className="px-3 py-2.5 text-helm-muted truncate max-w-[10rem]">{req.vendor_name || "—"}</td>
                  <td className="px-3 py-2.5 text-helm-muted truncate max-w-[10rem]">{personLabel(req.requester)}</td>
                  <td
                    className={cn(
                      "px-3 py-2.5 font-mono text-xs",
                      isExpectedDeliveryOverdue(req.expected_delivery_date, req.status)
                        ? "text-helm-status-negative"
                        : "text-helm-muted",
                    )}
                  >
                    {req.expected_delivery_date
                      ? (isExpectedDeliveryOverdue(req.expected_delivery_date, req.status)
                        ? `Overdue ${req.expected_delivery_date}`
                        : req.expected_delivery_date)
                      : "—"}
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge status={req.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && draft && (
        <GlassCard className="p-5 space-y-4" data-testid="procurement-detail">
          <div className="flex items-start justify-between gap-3">
            <div>
              <SectionLabel>Request detail</SectionLabel>
              <p className="text-helm-fg text-sm mt-1">{selected.item}</p>
              {(selected.blocking_production_orders || []).length > 0 && (
                <div className="mt-2">
                  <BlockingProductionBadge
                    orders={selected.blocking_production_orders}
                    requestId={selected.id}
                  />
                </div>
              )}
            </div>
            <button type="button" onClick={() => setSelectedId(null)} className="text-helm-muted hover:text-helm-fg">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Item</span>
              <input
                data-testid="procurement-edit-item"
                disabled={!canEditContent || busy}
                value={draft.item}
                onChange={(e) => setDraft((d) => ({ ...d, item: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Quantity</span>
              <input
                data-testid="procurement-edit-qty"
                disabled={!canEditContent || busy}
                value={draft.quantity}
                onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Vendor</span>
              <input
                data-testid="procurement-edit-vendor"
                disabled={!canEditContent || busy}
                value={draft.vendor_name}
                onChange={(e) => setDraft((d) => ({ ...d, vendor_name: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Cost</span>
              <input
                data-testid="procurement-edit-cost"
                disabled={!canEditContent || busy}
                value={draft.cost}
                onChange={(e) => setDraft((d) => ({ ...d, cost: e.target.value }))}
                placeholder="Optional"
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Expected delivery</span>
              <input
                data-testid="procurement-edit-expected-delivery"
                type="date"
                disabled={busy || !(canEditContent || canApprove)}
                value={draft.expected_delivery_date || ""}
                onChange={(e) => setDraft((d) => ({ ...d, expected_delivery_date: e.target.value }))}
                className={cn(
                  "w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm disabled:opacity-50",
                  isExpectedDeliveryOverdue(draft.expected_delivery_date, selected.status)
                    ? "text-helm-status-negative"
                    : "text-helm-fg",
                )}
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Notes</span>
            <textarea
              data-testid="procurement-edit-notes"
              disabled={!canEditContent || busy}
              value={draft.notes}
              onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
              rows={3}
              className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg disabled:opacity-50"
            />
          </label>

          <div className="flex flex-wrap gap-4 text-xs text-helm-muted">
            <span>Requester: <span className="text-helm-fg">{personLabel(selected.requester)}</span></span>
            <span>Approver: <span className="text-helm-fg">{personLabel(selected.approver)}</span></span>
            <span>Status: <StatusBadge status={selected.status} /></span>
          </div>

          <div className="flex flex-wrap gap-2">
            {(canEditContent || canApprove) && (
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-save-btn"
                onClick={() => saveRequest()}
                className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover disabled:opacity-50"
              >
                Save changes
              </button>
            )}
            {canApprove && selected.status === "requested" && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  data-testid="procurement-approve-btn"
                  onClick={() => setStatus("approved")}
                  className="rounded-md border border-helm-muted/40 text-helm-muted text-sm px-3 py-2 hover:bg-helm-muted/10 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={busy}
                  data-testid="procurement-reject-btn"
                  onClick={() => setStatus("rejected")}
                  className="rounded-md border border-helm-status-negative/40 text-helm-status-negative text-sm px-3 py-2 hover:bg-helm-status-negative/10 disabled:opacity-50"
                >
                  Reject
                </button>
              </>
            )}
            {selected.status === "approved" && (
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-ordered-btn"
                onClick={() => setStatus("ordered")}
                className="rounded-md border border-helm-status-warning/40 text-helm-status-warning text-sm px-3 py-2 hover:bg-helm-status-warning/10 disabled:opacity-50"
              >
                Mark ordered
              </button>
            )}
            {selected.status === "ordered" && (
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-delivered-btn"
                onClick={() => setStatus("delivered")}
                className="rounded-md border border-helm-status-positive/40 text-helm-status-positive text-sm px-3 py-2 hover:bg-helm-status-positive/10 disabled:opacity-50"
              >
                Mark delivered
              </button>
            )}
            {canDeleteSelected && (
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-delete-btn"
                onClick={() => setConfirmDelete(true)}
                className="inline-flex items-center gap-1.5 rounded-md border border-helm-status-negative/30 text-helm-status-negative text-sm px-3 py-2 hover:bg-helm-status-negative/10 disabled:opacity-50 ml-auto"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            )}
          </div>
        </GlassCard>
      )}

      {orderDatePrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="order-date-prompt">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => !busy && setOrderDatePrompt(null)} />
          <div className="relative w-full max-w-sm rounded-md border border-helm-line bg-helm-card p-5 space-y-3">
            <p className="text-sm font-medium text-helm-fg">Expected delivery date?</p>
            <p className="text-sm text-helm-muted leading-relaxed">
              Optional — add a vendor delivery date so Helm can flag this request if it runs late.
            </p>
            <input
              type="date"
              data-testid="order-date-prompt-input"
              value={orderDatePrompt.date}
              onChange={(e) => setOrderDatePrompt((s) => ({ ...s, date: e.target.value }))}
              className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
            />
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                disabled={busy}
                data-testid="order-date-prompt-skip"
                onClick={() => confirmOrderDatePrompt({ skip: true })}
                className="rounded-md border border-helm-line text-sm px-3 py-2 text-helm-fg"
              >
                Skip
              </button>
              <button
                type="button"
                disabled={busy}
                data-testid="order-date-prompt-confirm"
                onClick={() => confirmOrderDatePrompt()}
                className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
              >
                Save &amp; mark ordered
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete && Boolean(selected)}
        title={`Delete request “${selected?.item || ""}”?`}
        description="This permanently removes the purchase request. This can’t be undone."
        confirmLabel="Delete request"
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={deleteRequest}
        testId="delete-procurement-confirm"
      />

      {adding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => !busy && setAdding(false)} />
          <div className="relative w-full max-w-md rounded-md border border-helm-line bg-helm-card p-5 space-y-3" data-testid="procurement-create-modal">
            <div className="flex items-center justify-between">
              <p className="text-sm text-helm-fg font-medium">New purchase request</p>
              <button type="button" onClick={() => setAdding(false)} className="text-helm-muted hover:text-helm-fg">
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Item</span>
              <input
                data-testid="procurement-new-item"
                value={form.item}
                onChange={(e) => setForm((f) => ({ ...f, item: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                autoFocus
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block space-y-1">
                <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Quantity</span>
                <input
                  data-testid="procurement-new-qty"
                  value={form.quantity}
                  onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                  className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Cost</span>
                <input
                  data-testid="procurement-new-cost"
                  value={form.cost}
                  onChange={(e) => setForm((f) => ({ ...f, cost: e.target.value }))}
                  placeholder="Optional"
                  className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                />
              </label>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Vendor</span>
              <input
                data-testid="procurement-new-vendor"
                value={form.vendor_name}
                onChange={(e) => setForm((f) => ({ ...f, vendor_name: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Expected delivery</span>
              <input
                data-testid="procurement-new-expected-delivery"
                type="date"
                value={form.expected_delivery_date}
                onChange={(e) => setForm((f) => ({ ...f, expected_delivery_date: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Notes</span>
              <textarea
                data-testid="procurement-new-notes"
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
              />
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setAdding(false)} className="text-sm text-helm-muted px-3 py-2">Cancel</button>
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-create-submit"
                onClick={createRequest}
                className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover disabled:opacity-50"
              >
                Submit request
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
