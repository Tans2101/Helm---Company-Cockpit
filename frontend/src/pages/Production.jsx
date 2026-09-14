import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Plus, ChevronUp, ChevronDown, Trash2, X, User, ArrowRight, Settings2, Factory,
  List, Columns3,
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

/** high → normal → low; earlier due_date first; undated last. */
const PRIORITY_RANK = { high: 0, normal: 1, low: 2 };

function compareWorkOrders(a, b) {
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

/** Live duration from current_progress.entered_at — no history needed. */
function formatTimeInStage(enteredAt, stageName, nowMs = Date.now()) {
  if (!enteredAt) return null;
  const start = new Date(enteredAt).getTime();
  if (Number.isNaN(start)) return null;
  const seconds = Math.max(0, Math.floor((nowMs - start) / 1000));
  let duration;
  if (seconds < 60) duration = "just now";
  else if (seconds < 3600) {
    const m = Math.round(seconds / 60);
    duration = m === 1 ? "1 minute" : `${m} minutes`;
  } else if (seconds < 86400) {
    const h = Math.round(seconds / 3600);
    duration = h === 1 ? "1 hour" : `${h} hours`;
  } else {
    const d = Math.round(seconds / 86400);
    duration = d === 1 ? "1 day" : `${d} days`;
  }
  if (!stageName) return duration === "just now" ? "Just entered stage" : duration;
  if (duration === "just now") return `Just entered ${stageName}`;
  return `${duration} in ${stageName}`;
}

function isDueDateOverdue(dueDate, nowMs = Date.now()) {
  const raw = (dueDate || "").trim();
  if (!raw) return false;
  // YYYY-MM-DD → end of that local day
  const end = new Date(`${raw}T23:59:59`);
  if (Number.isNaN(end.getTime())) return false;
  return end.getTime() < nowMs;
}

const STAGE_PRESETS = [
  {
    id: "fabrication",
    label: "Fabrication",
    description: "Fabrication → Finishing → Inspection → Shipping",
    stages: ["Fabrication", "Finishing", "Inspection", "Shipping"],
  },
  {
    id: "assembly",
    label: "Assembly",
    description: "Cutting → Assembly → QA → Packaging",
    stages: ["Cutting", "Assembly", "QA", "Packaging"],
  },
  {
    id: "simple",
    label: "Simple flow",
    description: "Prep → In Progress → Review → Done",
    stages: ["Prep", "In Progress", "Review", "Done"],
  },
];

function StageStepper({ stages, currentStageId }) {
  const idx = stages.findIndex((s) => s.id === currentStageId);
  const currentName = idx >= 0 ? stages[idx].name : null;
  return (
    <div
      className="flex items-center gap-0.5 min-w-0"
      data-testid="stage-stepper"
      title={currentName ? `Stage: ${currentName}` : "Stage progress"}
    >
      {stages.map((stage, i) => {
        const filled = idx >= 0 && i <= idx;
        const current = i === idx;
        return (
          <div key={stage.id} className="flex items-center gap-0.5">
            <span
              data-testid={`stepper-dot-${stage.id}`}
              title={stage.name}
              className={cn(
                "block h-2 w-2 rounded-full shrink-0",
                filled ? "bg-helm-gold" : "bg-helm-muted/30",
                current && "ring-2 ring-helm-gold/35 ring-offset-1 ring-offset-helm-card",
              )}
            />
            {i < stages.length - 1 && (
              <span
                className={cn(
                  "block h-px w-2.5 sm:w-3.5 shrink-0",
                  idx >= 0 && i < idx ? "bg-helm-gold/55" : "bg-helm-muted/25",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function PriorityBadge({ priority }) {
  if (!priority || priority === "normal") return null;
  const high = priority === "high";
  return (
    <span
      data-testid={`priority-badge-${priority}`}
      className={cn(
        "shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide border",
        high
          ? "border-helm-gold/50 bg-helm-gold/15 text-helm-gold"
          : "border-helm-line bg-helm-fg/[0.03] text-helm-muted",
      )}
    >
      {priority}
    </span>
  );
}

function StagePresetsPanel({ onApply, onScratch, busy }) {
  return (
    <div className="w-full max-w-xl mx-auto space-y-4" data-testid="stage-presets">
      <div className="space-y-2">
        {STAGE_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            data-testid={`stage-preset-${preset.id}`}
            disabled={busy}
            onClick={() => onApply(preset)}
            className="w-full text-left rounded-xl border border-helm-line bg-helm-fg/[0.02] px-4 py-3 hover:border-helm-gold/40 transition-colors disabled:opacity-50"
          >
            <p className="text-sm text-helm-fg font-medium">{preset.label}</p>
            <p className="text-xs text-helm-muted mt-0.5">{preset.description}</p>
          </button>
        ))}
      </div>
      {onScratch && (
        <button
          type="button"
          data-testid="stage-preset-scratch"
          disabled={busy}
          onClick={onScratch}
          className="w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-helm-line bg-helm-fg/[0.03] text-sm text-helm-fg px-4 py-2.5 hover:border-helm-gold/40 disabled:opacity-50"
        >
          <Plus className="w-4 h-4" /> Start from scratch
        </button>
      )}
    </div>
  );
}

export default function Production() {
  const { data, loading, error, reload, setData } = useFetch("/production/work-orders");
  const { data: membersData } = useFetch("/members");
  const [view, setView] = useState("list"); // list | board | stages
  const [lastWorkView, setLastWorkView] = useState("list"); // list | board
  const [nowMs, setNowMs] = useState(() => Date.now());
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

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

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
    for (const sid of Object.keys(map)) {
      map[sid].sort(compareWorkOrders);
    }
    return map;
  }, [stages, workOrders]);
  const stageById = useMemo(() => {
    const map = {};
    for (const s of stages) map[s.id] = s;
    return map;
  }, [stages]);
  const sortedWorkOrders = useMemo(
    () => [...workOrders].sort(compareWorkOrders),
    [workOrders],
  );

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

  const applyStagePreset = async (preset) => {
    if (!preset?.stages?.length) return;
    setBusy(true);
    try {
      for (const name of preset.stages) {
        await api.post("/production/stages", { name });
      }
      toast.success(`Added “${preset.label}” stages — edit anytime`);
      setAddingStage(false);
      await reload();
      setView(lastWorkView || "list");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not apply stage preset");
      await reload();
    } finally {
      setBusy(false);
    }
  };

  const openStagesEditor = () => {
    if (view === "list" || view === "board") setLastWorkView(view);
    setView("stages");
  };

  const leaveStagesEditor = () => {
    setView(lastWorkView || "list");
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
    if (workOrders.length > 0) {
      const ok = window.confirm(
        `${workOrders.length} active work order${workOrders.length === 1 ? " is" : "s are"} on the board. `
        + "Reordering stages changes which stage Advance moves them to next. Continue?",
      );
      if (!ok) return;
    }
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
      {stages.length > 0 && view !== "stages" && (
        <div className="inline-flex rounded-md border border-helm-line overflow-hidden" data-testid="production-view-toggle">
          <button
            type="button"
            data-testid="production-view-list"
            onClick={() => { setView("list"); setLastWorkView("list"); }}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-2 text-sm",
              view === "list" ? "bg-helm-fg/[0.08] text-helm-fg" : "bg-helm-fg/[0.02] text-helm-muted hover:text-helm-fg",
            )}
          >
            <List className="w-4 h-4" /> List
          </button>
          <button
            type="button"
            data-testid="production-view-board"
            onClick={() => { setView("board"); setLastWorkView("board"); }}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-2 text-sm border-l border-helm-line",
              view === "board" ? "bg-helm-fg/[0.08] text-helm-fg" : "bg-helm-fg/[0.02] text-helm-muted hover:text-helm-fg",
            )}
          >
            <Columns3 className="w-4 h-4" /> Board
          </button>
        </div>
      )}
      {canStructure && (
        <button
          type="button"
          data-testid="edit-production-stages-btn"
          onClick={() => (view === "stages" ? leaveStagesEditor() : openStagesEditor())}
          className="inline-flex items-center gap-1.5 rounded-md border border-helm-line bg-helm-fg/[0.03] text-helm-fg text-sm px-3 py-2 hover:border-helm-gold/40"
        >
          <Settings2 className="w-4 h-4" />
          {view === "stages" ? "Back to work orders" : "Edit stages"}
        </button>
      )}
      {(view === "list" || view === "board") && stages.length > 0 && (
        <button
          type="button"
          data-testid="add-work-order-btn"
          onClick={() => setAddingOrder(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
        >
          <Plus className="w-4 h-4" /> New work order
        </button>
      )}
      {view === "stages" && canStructure && stages.length > 0 && (
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
            ? "Define the stage sequence for work orders. Start from a preset or build your own — you can edit anytime."
            : view === "board"
              ? "Board view — empty stages stay collapsed. Switch to List for a denser view of a few jobs."
              : "Each row is a work order: stage progress, time in the current stage, and Advance when ready."
        }
        action={headerAction}
      />

      {view === "stages" ? (
        <div data-testid="production-stages-editor">
          {stages.length === 0 ? (
            canStructure ? (
              <div className="py-8">
                <div className="text-center mb-6">
                  <div className="w-14 h-14 rounded-2xl bg-helm-navy/5 border border-helm-line flex items-center justify-center mb-5 mx-auto">
                    <Factory className="w-6 h-6 text-helm-gold" />
                  </div>
                  <h3 className="font-display text-xl text-helm-fg font-medium tracking-tight">Choose a starting sequence</h3>
                  <p className="text-sm text-helm-muted mt-2 max-w-sm mx-auto leading-relaxed">
                    One click sets up stages you can rename, reorder, or delete afterward.
                  </p>
                </div>
                <StagePresetsPanel
                  busy={busy}
                  onApply={applyStagePreset}
                  onScratch={() => setAddingStage(true)}
                />
              </div>
            ) : (
              <EmptyState
                icon={Factory}
                title="No stages yet"
                body="Ask a Production lead or the CEO to set up the sequence."
              />
            )
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
        canStructure ? (
          <div className="py-8" data-testid="production-empty-presets">
            <div className="text-center mb-6">
              <div className="w-14 h-14 rounded-2xl bg-helm-navy/5 border border-helm-line flex items-center justify-center mb-5 mx-auto">
                <Factory className="w-6 h-6 text-helm-gold" />
              </div>
              <h3 className="font-display text-xl text-helm-fg font-medium tracking-tight">Set up your production sequence</h3>
              <p className="text-sm text-helm-muted mt-2 max-w-sm mx-auto leading-relaxed">
                Pick a common flow to start — fully editable after — or build stages one by one.
              </p>
            </div>
            <StagePresetsPanel
              busy={busy}
              onApply={applyStagePreset}
              onScratch={() => { openStagesEditor(); setAddingStage(true); }}
            />
          </div>
        ) : (
          <EmptyState
            icon={Factory}
            title="Define your production sequence"
            body="Ask a Production lead or the CEO to define the stage sequence before work can start."
          />
        )
      ) : workOrders.length === 0 ? (
        <EmptyState
          icon={Factory}
          title="No work orders yet"
          body="Create a work order to track it through your stage sequence."
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
      ) : view === "list" ? (
        <div className="space-y-2" data-testid="production-list">
          {sortedWorkOrders.map((order) => {
            const progress = order.current_progress || {};
            const stage = stageById[order.current_stage_id];
            const stageName = stage?.name || "current stage";
            const timeLabel = formatTimeInStage(progress.entered_at, stageName, nowMs);
            const overdue = isDueDateOverdue(order.due_date, nowMs);
            const blocked = progress.status === "blocked" ? progress.blocked_reason : null;
            return (
              <GlassCard
                key={order.id}
                data-testid={`work-order-row-${order.id}`}
                className={cn(
                  "p-3 sm:p-4 cursor-pointer transition-colors hover:border-helm-gold/35",
                  selectedId === order.id && "border-helm-gold/45 bg-helm-gold/[0.04]",
                )}
                onClick={() => setSelectedId(order.id)}
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-4">
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-start gap-2 flex-wrap">
                      <p className="text-sm text-helm-fg font-medium leading-snug truncate">
                        {order.reference}
                      </p>
                      <PriorityBadge priority={order.priority} />
                      <StatusBadge status={progress.status} blockedReason={progress.blocked_reason} />
                    </div>
                    {(order.product || order.quantity != null || order.customer) && (
                      <p className="text-xs text-helm-muted truncate">
                        {[
                          order.product || null,
                          order.quantity != null ? `× ${order.quantity}` : null,
                          order.customer ? `· ${order.customer}` : null,
                        ].filter(Boolean).join(" ")}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
                      {timeLabel && (
                        <span className="font-mono text-helm-fg/80" data-testid={`time-in-stage-${order.id}`}>
                          {timeLabel}
                        </span>
                      )}
                      {order.due_date && (
                        <span
                          data-testid={`due-date-${order.id}`}
                          className={cn(
                            "font-mono",
                            overdue ? "text-helm-status-negative" : "text-helm-muted",
                          )}
                        >
                          {overdue ? "Overdue " : "Due "}{order.due_date}
                        </span>
                      )}
                      {blocked && (
                        <span className="text-helm-status-negative truncate" data-testid={`blocked-reason-${order.id}`}>
                          Blocked
                          {blocked.category ? ` · ${CATEGORY_LABELS[blocked.category] || blocked.category}` : ""}
                          {blocked.detail ? ` — ${blocked.detail}` : ""}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 lg:shrink-0">
                    <StageStepper stages={stages} currentStageId={order.current_stage_id} />
                    <button
                      type="button"
                      data-testid={`advance-work-order-${order.id}`}
                      disabled={busy}
                      onClick={(e) => advanceWorkOrder(order, e)}
                      className="inline-flex items-center justify-center gap-1.5 rounded-md border border-helm-line bg-helm-fg/[0.03] text-xs text-helm-fg px-2.5 py-1.5 hover:border-helm-gold/40 disabled:opacity-50 shrink-0"
                    >
                      Advance <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </GlassCard>
            );
          })}
        </div>
      ) : (
        <>
        {stageTimeAverages.length > 0 && (
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
            const empty = cards.length === 0;
            return (
              <div
                key={stage.id}
                data-testid={`production-column-${stage.id}`}
                data-empty={empty ? "true" : "false"}
                className={cn(
                  "shrink-0 flex flex-col transition-all",
                  empty ? "min-w-[4.5rem] w-[4.5rem]" : "min-w-[260px] w-[280px]",
                )}
              >
                <div className={cn("flex items-center justify-between mb-2 px-1", empty && "justify-center")}>
                  <div className="min-w-0">
                    <p
                      className={cn(
                        "text-sm font-medium",
                        empty ? "text-helm-muted text-[11px] truncate max-h-28" : "text-helm-fg truncate",
                      )}
                      style={empty ? { writingMode: "vertical-rl", transform: "rotate(180deg)" } : undefined}
                      title={stage.name}
                    >
                      {stage.name}
                    </p>
                    {!empty && (
                      <p className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">
                        {cards.length} {cards.length === 1 ? "order" : "orders"}
                      </p>
                    )}
                  </div>
                </div>
                <div
                  className={cn(
                    "flex-1 space-y-2 rounded-xl border p-2",
                    empty
                      ? "border-helm-line/40 bg-helm-fg/[0.01] min-h-[8rem] opacity-45"
                      : "border-helm-line/70 bg-helm-fg/[0.015] min-h-[12rem]",
                  )}
                >
                  {cards.map((order) => {
                    const progress = order.current_progress || {};
                    const linkedId = progress.linked_procurement_request_id;
                    const linked = linkedId ? procById[linkedId] : null;
                    const timeLabel = formatTimeInStage(
                      progress.entered_at,
                      stage.name,
                      nowMs,
                    );
                    const overdue = isDueDateOverdue(order.due_date, nowMs);
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
                            <PriorityBadge priority={order.priority} />
                          </div>
                          {(order.product || order.quantity != null) && (
                            <p className="text-xs text-helm-muted truncate">
                              {[order.product, order.quantity != null ? `× ${order.quantity}` : null]
                                .filter(Boolean)
                                .join(" ")}
                            </p>
                          )}
                          {timeLabel && (
                            <p className="text-[11px] font-mono text-helm-fg/75" data-testid={`time-in-stage-${order.id}`}>
                              {timeLabel}
                            </p>
                          )}
                          {order.due_date && (
                            <p className={cn("text-[11px] font-mono", overdue ? "text-helm-status-negative" : "text-helm-muted")}>
                              {overdue ? "Overdue " : "Due "}{order.due_date}
                            </p>
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

      {selected && draft && (view === "board" || view === "list") && (
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
