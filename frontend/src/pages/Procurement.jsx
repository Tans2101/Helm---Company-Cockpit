import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, X, Package } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  requested: { label: "Requested", className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30" },
  approved: { label: "Approved", className: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  ordered: { label: "Ordered", className: "bg-amber-500/15 text-amber-200 border-amber-500/30" },
  delivered: { label: "Delivered", className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  rejected: { label: "Rejected", className: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
};

const CLOSED = new Set(["delivered", "rejected"]);

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

export default function Procurement() {
  const { data, loading, error, reload } = useFetch("/procurement/requests");
  const [showClosed, setShowClosed] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ item: "", quantity: "1", vendor_name: "", cost: "", notes: "" });

  const allRequests = data?.requests || [];
  const visible = useMemo(
    () => (showClosed ? allRequests : allRequests.filter((r) => !CLOSED.has(r.status))),
    [allRequests, showClosed],
  );
  const selected = allRequests.find((r) => r.id === selectedId) || null;

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
      status: selected.status || "requested",
    });
  }, [selectedId, selected?.updated_at]);

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
      });
      toast.success("Request submitted");
      setForm({ item: "", quantity: "1", vendor_name: "", cost: "", notes: "" });
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

  const setStatus = async (status) => {
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/procurement/requests/${selected.id}`, { status });
      toast.success(`Marked ${STATUS_META[status]?.label || status}`);
      await reload();
      if (res?.request?.id) setSelectedId(res.request.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update status");
    } finally {
      setBusy(false);
    }
  };

  const deleteRequest = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete request “${selected.item}”?`)) return;
    setBusy(true);
    try {
      await api.delete(`/procurement/requests/${selected.id}`);
      toast.success("Request deleted");
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
      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover"
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
        <p className="text-xs text-zinc-500 font-mono">
          {visible.length} shown · {allRequests.length} total
        </p>
        <label className="inline-flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            data-testid="procurement-show-closed"
            checked={showClosed}
            onChange={(e) => setShowClosed(e.target.checked)}
            className="rounded border-white/20 bg-transparent"
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
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"
            >
              <Plus className="w-4 h-4" /> New request
            </button>
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-white/10 mb-6">
          <table className="w-full text-left text-sm" data-testid="procurement-table">
            <thead>
              <tr className="border-b border-white/10 text-[10px] font-mono uppercase tracking-wide text-zinc-500">
                <th className="px-3 py-2 font-medium">Item</th>
                <th className="px-3 py-2 font-medium">Qty</th>
                <th className="px-3 py-2 font-medium">Vendor</th>
                <th className="px-3 py-2 font-medium">Requester</th>
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
                    "border-b border-white/5 cursor-pointer transition-colors hover:bg-white/[0.03]",
                    selectedId === req.id && "bg-gold/[0.06]",
                  )}
                >
                  <td className="px-3 py-2.5 text-white truncate max-w-[14rem]">{req.item}</td>
                  <td className="px-3 py-2.5 text-zinc-300 font-mono text-xs">{req.quantity}</td>
                  <td className="px-3 py-2.5 text-zinc-400 truncate max-w-[10rem]">{req.vendor_name || "—"}</td>
                  <td className="px-3 py-2.5 text-zinc-400 truncate max-w-[10rem]">{personLabel(req.requester)}</td>
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
              <p className="text-white text-sm mt-1">{selected.item}</p>
            </div>
            <button type="button" onClick={() => setSelectedId(null)} className="text-zinc-500 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Item</span>
              <input
                data-testid="procurement-edit-item"
                disabled={!canEditContent || busy}
                value={draft.item}
                onChange={(e) => setDraft((d) => ({ ...d, item: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Quantity</span>
              <input
                data-testid="procurement-edit-qty"
                disabled={!canEditContent || busy}
                value={draft.quantity}
                onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Vendor</span>
              <input
                data-testid="procurement-edit-vendor"
                disabled={!canEditContent || busy}
                value={draft.vendor_name}
                onChange={(e) => setDraft((d) => ({ ...d, vendor_name: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Cost</span>
              <input
                data-testid="procurement-edit-cost"
                disabled={!canEditContent || busy}
                value={draft.cost}
                onChange={(e) => setDraft((d) => ({ ...d, cost: e.target.value }))}
                placeholder="Optional"
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Notes</span>
            <textarea
              data-testid="procurement-edit-notes"
              disabled={!canEditContent || busy}
              value={draft.notes}
              onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
              rows={3}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
            />
          </label>

          <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
            <span>Requester: <span className="text-zinc-300">{personLabel(selected.requester)}</span></span>
            <span>Approver: <span className="text-zinc-300">{personLabel(selected.approver)}</span></span>
            <span>Status: <StatusBadge status={selected.status} /></span>
          </div>

          <div className="flex flex-wrap gap-2">
            {canEditContent && (
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-save-btn"
                onClick={() => saveRequest()}
                className="rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
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
                  className="rounded-md border border-sky-500/40 text-sky-200 text-sm px-3 py-2 hover:bg-sky-500/10 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={busy}
                  data-testid="procurement-reject-btn"
                  onClick={() => setStatus("rejected")}
                  className="rounded-md border border-rose-500/40 text-rose-200 text-sm px-3 py-2 hover:bg-rose-500/10 disabled:opacity-50"
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
                className="rounded-md border border-amber-500/40 text-amber-200 text-sm px-3 py-2 hover:bg-amber-500/10 disabled:opacity-50"
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
                className="rounded-md border border-emerald-500/40 text-emerald-200 text-sm px-3 py-2 hover:bg-emerald-500/10 disabled:opacity-50"
              >
                Mark delivered
              </button>
            )}
            {canDeleteSelected && (
              <button
                type="button"
                disabled={busy}
                data-testid="procurement-delete-btn"
                onClick={deleteRequest}
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
          <div className="relative w-full max-w-md rounded-md border border-white/10 bg-[#141417] p-5 space-y-3" data-testid="procurement-create-modal">
            <div className="flex items-center justify-between">
              <p className="text-sm text-white font-medium">New purchase request</p>
              <button type="button" onClick={() => setAdding(false)} className="text-zinc-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Item</span>
              <input
                data-testid="procurement-new-item"
                value={form.item}
                onChange={(e) => setForm((f) => ({ ...f, item: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                autoFocus
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block space-y-1">
                <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Quantity</span>
                <input
                  data-testid="procurement-new-qty"
                  value={form.quantity}
                  onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                  className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Cost</span>
                <input
                  data-testid="procurement-new-cost"
                  value={form.cost}
                  onChange={(e) => setForm((f) => ({ ...f, cost: e.target.value }))}
                  placeholder="Optional"
                  className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                />
              </label>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Vendor</span>
              <input
                data-testid="procurement-new-vendor"
                value={form.vendor_name}
                onChange={(e) => setForm((f) => ({ ...f, vendor_name: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Notes</span>
              <textarea
                data-testid="procurement-new-notes"
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
                data-testid="procurement-create-submit"
                onClick={createRequest}
                className="rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
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
