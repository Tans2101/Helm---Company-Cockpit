import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Plus, ChevronUp, ChevronDown, Trash2, X, User, ArrowRight, Settings2, Factory,
} from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  not_started: { label: "Not started", className: "bg-helm-muted/15 text-helm-fg border-helm-muted/30" },
  in_progress: { label: "In progress", className: "bg-helm-muted/15 text-helm-muted border-helm-muted/30" },
  blocked: { label: "Blocked", className: "bg-helm-status-negative/15 text-helm-status-negative border-helm-status-negative/30" },
  done: { label: "Done", className: "bg-helm-status-positive/15 text-helm-status-positive border-helm-status-positive/30" },
};

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

const PROC_OPEN = new Set(["requested", "approved", "ordered"]);

function StatusBadge({ status, blockedReason }) {
  const meta = STATUS_META[status] || STATUS_META.not_started;
  const category = blockedReason?.category;
  const label =
    status === "blocked" && category
      ? `Blocked · ${CATEGORY_LABELS[category] || category}`
      : meta.label;
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide border", meta.className)}>
      {label}
    </span>
  );
}

function AssigneeChips({ assignees }) {
  const list = assignees || [];
  if (!list.length) return <span className="text-xs text-helm-muted">Unassigned</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {list.map((a) => (
        <span
          key={a.user_id}
          className="inline-flex items-center gap-1 rounded-full border border-helm-line bg-helm-fg/[0.03] pl-0.5 pr-2 py-0.5 text-[11px] text-helm-fg"
          title={a.email || a.name}
        >
          {a.picture ? (
            <img src={a.picture} alt="" className="w-4 h-4 rounded-full object-cover" />
          ) : (
            <span className="w-4 h-4 rounded-full bg-helm-fg/10 flex items-center justify-center">
              <User className="w-2.5 h-2.5 text-helm-muted" />
            </span>
          )}
          <span className="truncate max-w-[7rem]">{a.name || a.email || "Teammate"}</span>
        </span>
      ))}
    </div>
  );
}

function upsertWorkOrder(list, order) {
  const next = Array.isArray(list) ? [...list] : [];
  const idx = next.findIndex((o) => o.id === order.id);
  if (order.status && order.status !== "active") {
    if (idx >= 0) next.splice(idx, 1);
    return next;
  }
  if (idx >= 0) next[idx] = order;
  else next.unshift(order);
  return next;
}

/** Format average dwell time for display — informational, not a forecast. */
function formatAverageStageTime(seconds) {
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
  const mins = Math.max(1, Math.round(s / 60));
  return `${mins}m`;
}

export default function Production() {
  const { data, loading, error, reload, setData } = useFetch("/production/work-orders");
  const { data: membersData } = useFetch("/members");
  const [view, setView] = useState("board"); // board | stages
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [addingOrder, setAddingOrder] = useState(false);
  const [addingStage, setAddingStage] = useState(false);
  const [newStageName, setNewStageName] = useState("");
  const [newOrder, setNewOrder] = useState({
    reference: "",
    product: "",
    quantity: "",
    customer: "",
    priority: "normal",
    due_date: "",
  });
  const [procRequests, setProcRequests] = useState([]);

  const stages = useMemo(
    () => [...(data?.stages || [])].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)),
    [data?.stages],
  );
  const workOrders = useMemo(
    () => (data?.work_orders || []).filter((o) => o.status === "active"),
    [data?.work_orders],
  );
  const selected = useMemo(
    () => (data?.work_orders || []).find((o) => o.id === selectedId) || null,
    [data?.work_orders, selectedId],
  );
  const procById = useMemo(() => {
    const map = {};
    for (const r of procRequests) map[r.id] = r;
    return map;
  }, [procRequests]);
  const openProcurement = useMemo(
    () => procRequests.filter((r) => PROC_OPEN.has(r.status)),
    [procRequests],
  );
  const stageTimeAverages = useMemo(
    () => (data?.stage_time_averages || []).filter((row) => row?.stage_id && row.sample_count > 0),
    [data?.stage_time_averages],
  );
  const ordersByStage = useMemo(() => {
    const map = {};
    for (const s of stages) map[s.id] = [];
    for (const o of workOrders) {
      const sid = o.current_stage_id;
      if (!map[sid]) map[sid] = [];
      map[sid].push(o);
    }
    return map;
  }, [stages, workOrders]);

  useEffect(() => {
    let mounted = true;
    api.get("/procurement/requests")
      .then((r) => {
        if (mounted) setProcRequests(r.data?.requests || []);
      })
      .catch(() => {
        if (mounted) setProcRequests([]);
      });
    return () => { mounted = false; };
  }, [data?.department_id]);

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      return;
    }
    const progress = selected.current_progress || {};
    setDraft({
      reference: selected.reference || "",
      product: selected.product || "",
      quantity: selected.quantity == null ? "" : String(selected.quantity),
      customer: selected.customer || "",
      priority: selected.priority || "normal",
      due_date: selected.due_date || "",
      status: progress.status || "not_started",
      notes: progress.notes || "",
      assigned_user_ids: [...(progress.assigned_user_ids || [])],
      blocked_category: progress.blocked_reason?.category || "",
      blocked_detail: progress.blocked_reason?.detail || "",
      linked_procurement_request_id: progress.linked_procurement_request_id || "",
    });
  }, [selected]);

  if (loading) return <LoadingScreen label="Loading production board" />;
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

  const canStructure = Boolean(data?.can_edit_structure);
  const workspaceMembers = (membersData?.members || []).filter((m) => m.user_id && m.status === "active");
  const priorities = data?.priorities || ["low", "normal", "high"];
  const progressStatuses = data?.progress_statuses || Object.keys(STATUS_META);
  const blockedCategories = data?.blocked_categories || Object.keys(CATEGORY_LABELS);

  const applyWorkOrder = (order) => {
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        work_orders: upsertWorkOrder(prev.work_orders, order),
      };
    });
    if (order?.status && order.status !== "active" && selectedId === order.id) {
      setSelectedId(null);
    } else if (order?.id && order.status === "active") {
      setSelectedId(order.id);
    }
  };

  const createWorkOrder = async () => {
    if (!newOrder.reference.trim()) {
      toast.error("Reference is required");
      return;
    }
    setBusy(true);
    try {
      const body = {
        reference: newOrder.reference.trim(),
        product: newOrder.product.trim(),
        customer: newOrder.customer.trim(),
        priority: newOrder.priority || "normal",
        due_date: newOrder.due_date.trim(),
      };
      if (newOrder.quantity !== "") {
        const q = Number(newOrder.quantity);
        if (!Number.isNaN(q)) body.quantity = q;
      }
      const { data: res } = await api.post("/production/work-orders", body);
      toast.success("Work order created");
      setAddingOrder(false);
      setNewOrder({
        reference: "", product: "", quantity: "", customer: "", priority: "normal", due_date: "",
      });
      if (res?.work_order) applyWorkOrder(res.work_order);
      else await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create work order");
    } finally {
      setBusy(false);
    }
  };

  const saveWorkOrder = async () => {
    if (!selected || !draft) return;
    setBusy(true);
    try {
      const orderBody = {
        reference: draft.reference.trim(),
        product: draft.product.trim(),
        customer: draft.customer.trim(),
        priority: draft.priority,
        due_date: draft.due_date.trim(),
      };
      if (draft.quantity === "") orderBody.quantity = null;
      else {
        const q = Number(draft.quantity);
        if (!Number.isNaN(q)) orderBody.quantity = q;
      }
      const stageBody = {
        status: draft.status,
        notes: draft.notes,
        assigned_user_ids: draft.assigned_user_ids,
      };
      if (draft.status === "blocked") {
        stageBody.blocked_reason = {
          category: draft.blocked_category,
          detail: draft.blocked_detail,
        };
        stageBody.linked_procurement_request_id =
          draft.blocked_category === "material"
            ? (draft.linked_procurement_request_id || "")
            : "";
      } else {
        stageBody.blocked_reason = null;
        stageBody.linked_procurement_request_id = "";
      }

      const [{ data: orderRes }, { data: stageRes }] = await Promise.all([
        api.patch(`/production/work-orders/${selected.id}`, orderBody),
        api.patch(`/production/work-orders/${selected.id}/stage`, stageBody),
      ]);
      toast.success("Work order updated");
      const updated = stageRes?.work_order || orderRes?.work_order;
      if (updated) applyWorkOrder(updated);
      else await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update work order");
    } finally {
      setBusy(false);
    }
  };

  const advanceWorkOrder = async (order, event) => {
    event?.stopPropagation?.();
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/production/work-orders/${order.id}/advance`);
      const updated = res?.work_order;
      if (updated?.status === "done") toast.success("Work order completed");
      else toast.success("Advanced to next stage");
      if (updated) applyWorkOrder(updated);
      else await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not advance");
    } finally {
      setBusy(false);
    }
  };

  const createStage = async () => {
    if (!newStageName.trim()) {
      toast.error("Stage name is required");
      return;
    }
    setBusy(true);
    try {
      await api.post("/production/stages", { name: newStageName.trim() });
      toast.success("Stage added");
      setNewStageName("");
      setAddingStage(false);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add stage");
    } finally {
      setBusy(false);
    }
  };

  const renameStage = async (stage, name) => {
    const trimmed = (name || "").trim();
    if (!trimmed || trimmed === stage.name) return;
    setBusy(true);
    try {
      await api.patch(`/production/stages/${stage.id}`, { name: trimmed });
      toast.success("Stage renamed");
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not rename");
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

  const headerAction = (
    <div className="flex items-center gap-2 flex-wrap justify-end">
      {canStructure && (
        <button
          type="button"
          data-testid="edit-production-stages-btn"
          onClick={() => setView((v) => (v === "stages" ? "board" : "stages"))}
          className="inline-flex items-center gap-1.5 rounded-md border border-helm-line bg-helm-fg/[0.03] text-helm-fg text-sm px-3 py-2 hover:border-helm-gold/40"
        >
          <Settings2 className="w-4 h-4" />
          {view === "stages" ? "Back to board" : "Edit stages"}
        </button>
      )}
      {view === "board" && stages.length > 0 && (
        <button
          type="button"
          data-testid="add-work-order-btn"
          onClick={() => setAddingOrder(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
        >
          <Plus className="w-4 h-4" /> New work order
        </button>
      )}
      {view === "stages" && canStructure && (
        <button
          type="button"
          data-testid="add-production-stage-btn"
          onClick={() => setAddingStage(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
        >
          <Plus className="w-4 h-4" /> Add stage
        </button>
      )}
    </div>
  );

  return (
    <div data-testid="production-page">
      <PageHeader
        title={data?.name || "Production"}
        subtitle={
          view === "stages"
            ? "Define the stage sequence for work orders. This is setup — daily work happens on the board."
            : "Work orders move across stage columns. Advance a card when its stage is finished."
        }
        action={headerAction}
      />

      {view === "stages" ? (
        <div data-testid="production-stages-editor">
          {stages.length === 0 ? (
            <EmptyState
              icon={Factory}
              title="No stages yet"
              body={canStructure ? "Add the first stage to define your production sequence." : "Ask a Production lead or the CEO to set up the sequence."}
              action={canStructure ? (
                <button
                  type="button"
                  onClick={() => setAddingStage(true)}
                  className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2 hover:bg-helm-gold-hover"
                >
                  <Plus className="w-4 h-4" /> Add first stage
                </button>
              ) : null}
            />
          ) : (
            <div className="space-y-3 mb-6">
              {stages.map((stage, index) => (
                <GlassCard key={stage.id} className="p-4" data-testid={`production-stage-${stage.id}`}>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-md border border-helm-line bg-helm-fg/[0.03] flex items-center justify-center font-mono text-xs text-helm-muted shrink-0">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0 space-y-2">
                      <input
                        data-testid={`stage-name-input-${stage.id}`}
                        defaultValue={stage.name}
                        disabled={!canStructure || busy}
                        onBlur={(e) => renameStage(stage, e.target.value)}
                        className="w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2 disabled:opacity-60"
                      />
                      <AssigneeChips assignees={stage.assignees} />
                    </div>
                    {canStructure && (
                      <div className="flex flex-col gap-0.5 shrink-0">
                        <button
                          type="button"
                          disabled={busy || index === 0}
                          data-testid={`stage-up-${stage.id}`}
                          onClick={() => moveStage(stage, -1)}
                          className="p-1 text-helm-muted hover:text-helm-fg disabled:opacity-30"
                          title="Move earlier"
                        >
                          <ChevronUp className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          disabled={busy || index === stages.length - 1}
                          data-testid={`stage-down-${stage.id}`}
                          onClick={() => moveStage(stage, 1)}
                          className="p-1 text-helm-muted hover:text-helm-fg disabled:opacity-30"
                          title="Move later"
                        >
                          <ChevronDown className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          data-testid={`stage-delete-${stage.id}`}
                          onClick={() => deleteStage(stage)}
                          className="p-1 text-helm-status-negative/80 hover:text-helm-status-negative disabled:opacity-30"
                          title="Delete stage"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </GlassCard>
              ))}
            </div>
          )}
        </div>
      ) : stages.length === 0 ? (
        <EmptyState
          icon={Factory}
          title="Define your production sequence"
          body={
            canStructure
              ? "Add stage templates first — then create work orders that move across them."
              : "Ask a Production lead or the CEO to define the stage sequence before work can start."
          }
          action={canStructure ? (
            <button
              type="button"
              data-testid="open-edit-stages-empty"
              onClick={() => { setView("stages"); setAddingStage(true); }}
              className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2 hover:bg-helm-gold-hover"
            >
              <Settings2 className="w-4 h-4" /> Edit stages
            </button>
          ) : null}
        />
      ) : workOrders.length === 0 ? (
        <EmptyState
          icon={Factory}
          title="No work orders yet"
          body="Create a work order to place it on the first stage of the board."
          action={(
            <button
              type="button"
              data-testid="add-work-order-empty"
              onClick={() => setAddingOrder(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2 hover:bg-helm-gold-hover"
            >
              <Plus className="w-4 h-4" /> New work order
            </button>
          )}
        />
      ) : (
        <>
        {view === "board" && stageTimeAverages.length > 0 && (
          <p
            className="mb-3 text-xs text-helm-muted"
            data-testid="stage-time-averages"
          >
            <span className="font-mono uppercase tracking-wide text-[10px] mr-2">Average time in stage</span>
            {stageTimeAverages.map((row, i) => {
              const label = formatAverageStageTime(row.average_seconds);
              if (!label) return null;
              return (
                <span key={row.stage_id}>
                  {i > 0 ? <span className="mx-1.5 text-helm-line">·</span> : null}
                  <span data-testid={`stage-avg-${row.stage_id}`}>
                    {row.stage_name || row.stage_id} {label}
                  </span>
                </span>
              );
            })}
          </p>
        )}
        <div
          className="flex gap-3 overflow-x-auto pb-4 -mx-1 px-1"
          data-testid="production-board"
        >
          {stages.map((stage) => {
            const cards = ordersByStage[stage.id] || [];
            return (
              <div
                key={stage.id}
                data-testid={`production-column-${stage.id}`}
                className="min-w-[260px] w-[280px] shrink-0 flex flex-col"
              >
                <div className="flex items-center justify-between mb-2 px-1">
                  <div className="min-w-0">
                    <p className="text-sm text-helm-fg truncate font-medium">{stage.name}</p>
                    <p className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">
                      {cards.length} {cards.length === 1 ? "order" : "orders"}
                    </p>
                  </div>
                </div>
                <div className="flex-1 space-y-2 rounded-xl border border-helm-line/70 bg-helm-fg/[0.015] p-2 min-h-[12rem]">
                  {cards.map((order) => {
                    const progress = order.current_progress || {};
                    const linkedId = progress.linked_procurement_request_id;
                    const linked = linkedId ? procById[linkedId] : null;
                    return (
                      <GlassCard
                        key={order.id}
                        data-testid={`work-order-card-${order.id}`}
                        className={cn(
                          "p-3 cursor-pointer transition-colors hover:border-helm-gold/35",
                          selectedId === order.id && "border-helm-gold/45 bg-helm-gold/[0.04]",
                        )}
                        onClick={() => setSelectedId(order.id)}
                      >
                        <div className="space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm text-helm-fg font-medium leading-snug truncate">
                              {order.reference}
                            </p>
                            {order.priority === "high" && (
                              <span
                                data-testid={`priority-high-${order.id}`}
                                className="shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide border border-helm-gold/50 bg-helm-gold/15 text-helm-gold"
                              >
                                High
                              </span>
                            )}
                          </div>
                          {(order.product || order.quantity != null) && (
                            <p className="text-xs text-helm-muted truncate">
                              {[order.product, order.quantity != null ? `× ${order.quantity}` : null]
                                .filter(Boolean)
                                .join(" ")}
                            </p>
                          )}
                          {order.due_date && (
                            <p className="text-[11px] font-mono text-helm-muted">Due {order.due_date}</p>
                          )}
                          <StatusBadge status={progress.status} blockedReason={progress.blocked_reason} />
                          {linked && (
                            <p className="text-[11px] text-helm-muted truncate" data-testid={`linked-proc-${order.id}`}>
                              Procurement: {linked.item || linked.id} · {PROC_STATUS_LABELS[linked.status] || linked.status}
                            </p>
                          )}
                          <AssigneeChips assignees={progress.assignees} />
                          <button
                            type="button"
                            data-testid={`advance-work-order-${order.id}`}
                            disabled={busy}
                            onClick={(e) => advanceWorkOrder(order, e)}
                            className="w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-helm-line bg-helm-fg/[0.03] text-xs text-helm-fg px-2 py-1.5 hover:border-helm-gold/40 disabled:opacity-50"
                          >
                            Advance <ArrowRight className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </GlassCard>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
        </>
      )}

      {selected && draft && view === "board" && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => setSelectedId(null)} />
          <GlassCard className="relative w-full sm:max-w-lg max-h-[90vh] overflow-y-auto m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="work-order-panel">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-helm-fg font-light">Work order</h3>
              <button type="button" onClick={() => setSelectedId(null)} className="text-helm-muted hover:text-helm-fg">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3">
              <label className="block text-xs text-helm-muted">Reference
                <input
                  data-testid="wo-reference-input"
                  value={draft.reference}
                  onChange={(e) => setDraft((d) => ({ ...d, reference: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-helm-muted">Product
                  <input
                    data-testid="wo-product-input"
                    value={draft.product}
                    onChange={(e) => setDraft((d) => ({ ...d, product: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
                <label className="block text-xs text-helm-muted">Quantity
                  <input
                    data-testid="wo-quantity-input"
                    type="number"
                    value={draft.quantity}
                    onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-helm-muted">Customer
                  <input
                    data-testid="wo-customer-input"
                    value={draft.customer}
                    onChange={(e) => setDraft((d) => ({ ...d, customer: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
                <label className="block text-xs text-helm-muted">Priority
                  <select
                    data-testid="wo-priority-select"
                    value={draft.priority}
                    onChange={(e) => setDraft((d) => ({ ...d, priority: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  >
                    {priorities.map((p) => (
                      <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block text-xs text-helm-muted">Due date
                <input
                  data-testid="wo-due-date-input"
                  type="date"
                  value={draft.due_date}
                  onChange={(e) => setDraft((d) => ({ ...d, due_date: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                />
              </label>

              <div className="pt-2 border-t border-helm-line">
                <SectionLabel className="mb-2">Current stage</SectionLabel>
                <label className="block text-xs text-helm-muted">Status
                  <select
                    data-testid="wo-stage-status-select"
                    value={draft.status}
                    onChange={(e) => setDraft((d) => ({ ...d, status: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  >
                    {progressStatuses.map((id) => (
                      <option key={id} value={id}>{STATUS_META[id]?.label || id}</option>
                    ))}
                  </select>
                </label>
                {draft.status === "blocked" && (
                  <div className="mt-3 space-y-3">
                    <label className="block text-xs text-helm-muted">Blocked reason
                      <select
                        data-testid="wo-blocked-category"
                        value={draft.blocked_category}
                        onChange={(e) => setDraft((d) => ({ ...d, blocked_category: e.target.value }))}
                        className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                      >
                        <option value="">Select category…</option>
                        {blockedCategories.map((c) => (
                          <option key={c} value={c}>{CATEGORY_LABELS[c] || c}</option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-xs text-helm-muted">Detail
                      <input
                        data-testid="wo-blocked-detail"
                        value={draft.blocked_detail}
                        onChange={(e) => setDraft((d) => ({ ...d, blocked_detail: e.target.value }))}
                        placeholder="What’s holding this up?"
                        className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                      />
                    </label>
                    {draft.blocked_category === "material" && (
                      <label className="block text-xs text-helm-muted">Linked procurement request
                        <select
                          data-testid="wo-linked-procurement"
                          value={draft.linked_procurement_request_id}
                          onChange={(e) => setDraft((d) => ({ ...d, linked_procurement_request_id: e.target.value }))}
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
                    )}
                  </div>
                )}
                <div className="mt-3">
                  <SectionLabel className="mb-2">Assignees</SectionLabel>
                  <div className="max-h-36 overflow-y-auto space-y-1.5 rounded-md border border-helm-line p-2">
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
                <label className="block text-xs text-helm-muted mt-3">Notes
                  <textarea
                    data-testid="wo-notes-input"
                    value={draft.notes}
                    onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                    rows={3}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2 resize-y"
                  />
                </label>
              </div>
            </div>
            <div className="mt-5 flex items-center gap-2">
              <button
                type="button"
                data-testid="save-work-order-btn"
                disabled={busy}
                onClick={saveWorkOrder}
                className="flex-1 rounded-md bg-helm-gold text-helm-navy font-medium py-2.5 text-sm hover:bg-helm-gold-hover disabled:opacity-60"
              >
                {busy ? "Saving…" : "Save changes"}
              </button>
              <button
                type="button"
                data-testid="advance-from-panel-btn"
                disabled={busy}
                onClick={() => advanceWorkOrder(selected)}
                className="inline-flex items-center gap-1.5 rounded-md border border-helm-line px-3 py-2.5 text-sm text-helm-fg hover:border-helm-gold/40 disabled:opacity-60"
              >
                Advance <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </GlassCard>
        </div>
      )}

      {addingOrder && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => setAddingOrder(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="add-work-order-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-helm-fg font-light">New work order</h3>
              <button type="button" onClick={() => setAddingOrder(false)} className="text-helm-muted hover:text-helm-fg"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <label className="block text-xs text-helm-muted">Reference
                <input
                  data-testid="new-wo-reference"
                  value={newOrder.reference}
                  onChange={(e) => setNewOrder((o) => ({ ...o, reference: e.target.value }))}
                  placeholder="Order #245"
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-helm-muted">Product
                  <input
                    data-testid="new-wo-product"
                    value={newOrder.product}
                    onChange={(e) => setNewOrder((o) => ({ ...o, product: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
                <label className="block text-xs text-helm-muted">Quantity
                  <input
                    data-testid="new-wo-quantity"
                    type="number"
                    value={newOrder.quantity}
                    onChange={(e) => setNewOrder((o) => ({ ...o, quantity: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
              </div>
              <label className="block text-xs text-helm-muted">Customer
                <input
                  data-testid="new-wo-customer"
                  value={newOrder.customer}
                  onChange={(e) => setNewOrder((o) => ({ ...o, customer: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-helm-muted">Priority
                  <select
                    data-testid="new-wo-priority"
                    value={newOrder.priority}
                    onChange={(e) => setNewOrder((o) => ({ ...o, priority: e.target.value }))}
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
                    value={newOrder.due_date}
                    onChange={(e) => setNewOrder((o) => ({ ...o, due_date: e.target.value }))}
                    className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
                  />
                </label>
              </div>
            </div>
            <button
              type="button"
              data-testid="submit-new-work-order"
              disabled={busy}
              onClick={createWorkOrder}
              className="mt-5 w-full rounded-md bg-helm-gold text-helm-navy font-medium py-2.5 text-sm hover:bg-helm-gold-hover disabled:opacity-60"
            >
              {busy ? "Creating…" : "Create work order"}
            </button>
          </GlassCard>
        </div>
      )}

      {addingStage && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => setAddingStage(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="add-stage-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-helm-fg font-light">Add stage</h3>
              <button type="button" onClick={() => setAddingStage(false)} className="text-helm-muted hover:text-helm-fg"><X className="w-5 h-5" /></button>
            </div>
            <label className="block text-xs text-helm-muted">Name
              <input
                data-testid="new-stage-name"
                value={newStageName}
                onChange={(e) => setNewStageName(e.target.value)}
                placeholder="e.g. Cut & prep"
                className="mt-1 w-full rounded-md border border-helm-line bg-helm-card text-helm-fg text-sm px-3 py-2"
              />
            </label>
            <button
              type="button"
              data-testid="submit-new-stage"
              disabled={busy}
              onClick={createStage}
              className="mt-5 w-full rounded-md bg-helm-gold text-helm-navy font-medium py-2.5 text-sm hover:bg-helm-gold-hover disabled:opacity-60"
            >
              {busy ? "Adding…" : "Add to sequence"}
            </button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
