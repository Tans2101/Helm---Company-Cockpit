import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, X, Users, ChevronUp, ChevronDown } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STEP_STATUS_META = {
  not_started: { label: "Not started", className: "bg-helm-muted/15 text-helm-fg border-helm-muted/30" },
  in_progress: { label: "In progress", className: "bg-helm-muted/15 text-helm-muted border-helm-muted/30" },
  done: { label: "Done", className: "bg-helm-status-positive/15 text-helm-status-positive border-helm-status-positive/30" },
};

function StepBadge({ status }) {
  const meta = STEP_STATUS_META[status] || STEP_STATUS_META.not_started;
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide border", meta.className)}>
      {meta.label}
    </span>
  );
}

function personLabel(p) {
  if (!p) return "Unassigned";
  return p.name || p.email || "Teammate";
}

export default function HR() {
  const { data, loading, error, reload } = useFetch("/hr/onboarding");
  const { data: tmplData, reload: reloadTmpl } = useFetch("/hr/template");
  const { data: membersData } = useFetch("/members");
  const [showActive, setShowActive] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(false);
  const [form, setForm] = useState({ hire_name: "", hire_email: "" });
  const [tmplDraft, setTmplDraft] = useState([]);

  const all = useMemo(() => data?.instances || [], [data?.instances]);
  const visible = useMemo(
    () => (showActive ? all : all.filter((i) => i.overall_status !== "active")),
    [all, showActive],
  );
  const selected = all.find((i) => i.id === selectedId) || null;
  const workspaceMembers = (membersData?.members || []).filter((m) => m.user_id && m.status === "active");
  const isLead = Boolean(data?.is_lead || tmplData?.can_edit_template);
  const myId = data?.my_user_id;
  const templateSteps = tmplData?.template?.steps;
  const templateUpdatedAt = tmplData?.template?.updated_at;

  useEffect(() => {
    const steps = templateSteps || [];
    setTmplDraft(steps.map((s) => ({ ...s })));
  }, [templateUpdatedAt, editingTemplate, templateSteps]);

  if (loading) return <LoadingScreen label="Loading HR onboarding" />;
  if (error) {
    const status = error?.response?.status;
    if (status === 403) {
      return (
        <ErrorScreen
          label="Access denied"
          message="You are not a member of HR. Ask your CEO to add you."
          onRetry={reload}
        />
      );
    }
    if (status === 404) {
      return (
        <ErrorScreen
          label="HR not enabled"
          message="Enable HR under Settings → Departments first."
          onRetry={reload}
        />
      );
    }
    return (
      <ErrorScreen
        label="Could not load HR"
        message={fetchErrorMessage(error, "HR data is unavailable.")}
        onRetry={reload}
      />
    );
  }

  const createInstance = async () => {
    if (!form.hire_name.trim()) {
      toast.error("Hire name is required");
      return;
    }
    setBusy(true);
    try {
      const { data: res } = await api.post("/hr/onboarding", {
        hire_name: form.hire_name.trim(),
        hire_email: form.hire_email.trim(),
      });
      toast.success("Onboarding started");
      setForm({ hire_name: "", hire_email: "" });
      setAdding(false);
      await reload();
      if (res?.instance?.id) setSelectedId(res.instance.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create onboarding");
    } finally {
      setBusy(false);
    }
  };

  const patchStep = async (step, patch) => {
    if (!selected) return;
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/hr/onboarding/${selected.id}`, {
        step_id: step.id,
        ...patch,
      });
      await reload();
      if (res?.instance?.id) setSelectedId(res.instance.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update step");
    } finally {
      setBusy(false);
    }
  };

  const deleteInstance = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete onboarding for “${selected.hire_name}”?`)) return;
    setBusy(true);
    try {
      await api.delete(`/hr/onboarding/${selected.id}`);
      toast.success("Onboarding deleted");
      setSelectedId(null);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
    } finally {
      setBusy(false);
    }
  };

  const saveTemplate = async () => {
    const steps = tmplDraft
      .map((s, i) => ({ id: s.id, name: (s.name || "").trim(), order: i }))
      .filter((s) => s.name);
    if (!steps.length) {
      toast.error("Template needs at least one step");
      return;
    }
    setBusy(true);
    try {
      await api.patch("/hr/template", { steps });
      toast.success("Template updated");
      setEditingTemplate(false);
      await reloadTmpl();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save template");
    } finally {
      setBusy(false);
    }
  };

  const moveTmplStep = (idx, dir) => {
    const next = [...tmplDraft];
    const j = idx + dir;
    if (j < 0 || j >= next.length) return;
    [next[idx], next[j]] = [next[j], next[idx]];
    setTmplDraft(next);
  };

  return (
    <div data-testid="hr-page">
      <PageHeader
        title={data?.name || "HR"}
        subtitle="Per-hire onboarding — each new hire gets their own checklist."
        action={(
          <div className="flex items-center gap-2">
            {isLead && (
              <button
                type="button"
                data-testid="hr-edit-template-btn"
                onClick={() => setEditingTemplate(true)}
                className="rounded-md border border-helm-fg/15 text-helm-fg text-sm px-3 py-2 hover:bg-helm-fg/5"
              >
                Edit template
              </button>
            )}
            {isLead && (
              <button
                type="button"
                data-testid="hr-add-onboarding-btn"
                onClick={() => setAdding(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover"
              >
                <Plus className="w-4 h-4" /> New hire
              </button>
            )}
          </div>
        )}
      />

      <div className="flex items-center justify-between gap-3 mb-4">
        <p className="text-xs text-helm-muted font-mono">
          {visible.length} shown · {all.length} total
        </p>
        <label className="inline-flex items-center gap-2 text-xs text-helm-muted cursor-pointer select-none">
          <input
            type="checkbox"
            data-testid="hr-show-active"
            checked={showActive}
            onChange={(e) => setShowActive(e.target.checked)}
            className="rounded border-helm-fg/20 bg-transparent"
          />
          Show completed (active)
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Users}
          title={all.length ? "No open onboardings" : "No onboardings yet"}
          body={
            all.length
              ? "Turn on “Show completed” to see finished hires, or start a new one."
              : isLead
                ? "Start onboarding for a new hire — their checklist is copied from the template."
                : "Ask an HR lead or the CEO to start onboarding for a new hire."
          }
          action={isLead ? (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2 hover:bg-helm-gold-hover"
            >
              <Plus className="w-4 h-4" /> New hire
            </button>
          ) : null}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-helm-line mb-6">
          <table className="w-full text-left text-sm" data-testid="hr-table">
            <thead>
              <tr className="border-b border-helm-line text-[10px] font-mono uppercase tracking-wide text-helm-muted">
                <th className="px-3 py-2 font-medium">Hire</th>
                <th className="px-3 py-2 font-medium">Progress</th>
                <th className="px-3 py-2 font-medium">Open steps</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((inst) => {
                const open = (inst.steps || []).filter((s) => s.status !== "done");
                return (
                  <tr
                    key={inst.id}
                    data-testid={`hr-row-${inst.id}`}
                    onClick={() => setSelectedId(inst.id)}
                    className={cn(
                      "border-b border-helm-line cursor-pointer transition-colors hover:bg-helm-fg/[0.03]",
                      selectedId === inst.id && "bg-helm-gold/[0.06]",
                    )}
                  >
                    <td className="px-3 py-2.5">
                      <p className="text-helm-fg truncate max-w-[14rem]">{inst.hire_name}</p>
                      {inst.hire_email && (
                        <p className="text-[11px] text-helm-muted truncate">{inst.hire_email}</p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-helm-muted font-mono text-xs">
                      {inst.progress?.done || 0}/{inst.progress?.total || 0}
                    </td>
                    <td className="px-3 py-2.5 text-helm-muted truncate max-w-[14rem] text-xs">
                      {open.length ? open.map((s) => s.name).join(", ") : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={cn(
                        "text-[10px] font-mono uppercase tracking-wide",
                        inst.overall_status === "active" ? "text-helm-status-positive" : "text-helm-muted",
                      )}
                      >
                        {inst.overall_status === "active" ? "Active" : "In progress"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <GlassCard className="p-5 space-y-4" data-testid="hr-detail">
          <div className="flex items-start justify-between gap-3">
            <div>
              <SectionLabel>Onboarding checklist</SectionLabel>
              <p className="text-helm-fg text-sm mt-1">{selected.hire_name}</p>
              {selected.hire_email && (
                <p className="text-xs text-helm-muted">{selected.hire_email}</p>
              )}
            </div>
            <button type="button" onClick={() => setSelectedId(null)} className="text-helm-muted hover:text-helm-fg">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-2" data-testid="hr-steps">
            {[...(selected.steps || [])].sort((a, b) => (a.order || 0) - (b.order || 0)).map((step) => {
              const canEditStep = isLead || step.assigned_to === myId;
              return (
                <div
                  key={step.id}
                  data-testid={`hr-step-${step.id}`}
                  className="rounded-md border border-helm-line bg-helm-fg/[0.02] p-3 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <p className="text-sm text-helm-fg">{step.name}</p>
                    <StepBadge status={step.status} />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <label className="space-y-1">
                      <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Status</span>
                      <select
                        disabled={!canEditStep || busy}
                        value={step.status}
                        onChange={(e) => patchStep(step, { status: e.target.value })}
                        className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-2 py-1.5 text-sm text-helm-fg disabled:opacity-50"
                      >
                        {(data?.step_statuses || ["not_started", "in_progress", "done"]).map((s) => (
                          <option key={s} value={s}>{STEP_STATUS_META[s]?.label || s}</option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Assignee</span>
                      <select
                        disabled={!isLead || busy}
                        value={step.assigned_to || ""}
                        onChange={(e) => patchStep(step, { assigned_to: e.target.value || null })}
                        className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-2 py-1.5 text-sm text-helm-fg disabled:opacity-50"
                      >
                        <option value="">Unassigned</option>
                        {workspaceMembers.map((m) => (
                          <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <p className="text-[11px] text-helm-muted">Assignee: {personLabel(step.assignee)}</p>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-2 text-xs text-helm-muted">
            <span>
              Overall:{" "}
              <span className={selected.overall_status === "active" ? "text-helm-status-positive" : "text-helm-muted"}>
                {selected.overall_status === "active" ? "Active" : "In progress"}
              </span>
            </span>
            <span className="font-mono">
              {selected.progress?.done || 0}/{selected.progress?.total || 0} steps done
            </span>
            {isLead && (
              <button
                type="button"
                disabled={busy}
                data-testid="hr-delete-btn"
                onClick={deleteInstance}
                className="inline-flex items-center gap-1.5 rounded-md border border-helm-status-negative/30 text-helm-status-negative text-sm px-3 py-1.5 hover:bg-helm-status-negative/10 disabled:opacity-50 ml-auto"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            )}
          </div>
        </GlassCard>
      )}

      {adding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => !busy && setAdding(false)} />
          <div className="relative w-full max-w-md rounded-md border border-helm-line bg-helm-card p-5 space-y-3" data-testid="hr-create-modal">
            <div className="flex items-center justify-between">
              <p className="text-sm text-helm-fg font-medium">Start onboarding</p>
              <button type="button" onClick={() => setAdding(false)} className="text-helm-muted hover:text-helm-fg">
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Hire name</span>
              <input
                data-testid="hr-new-name"
                value={form.hire_name}
                onChange={(e) => setForm((f) => ({ ...f, hire_name: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                autoFocus
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-helm-muted">Email</span>
              <input
                data-testid="hr-new-email"
                value={form.hire_email}
                onChange={(e) => setForm((f) => ({ ...f, hire_email: e.target.value }))}
                className="w-full rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
              />
            </label>
            <p className="text-[11px] text-helm-muted">
              Checklist will be copied from the current template ({(tmplData?.template?.steps || []).length} steps).
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setAdding(false)} className="text-sm text-helm-muted px-3 py-2">Cancel</button>
              <button
                type="button"
                disabled={busy}
                data-testid="hr-create-submit"
                onClick={createInstance}
                className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover disabled:opacity-50"
              >
                Start onboarding
              </button>
            </div>
          </div>
        </div>
      )}

      {editingTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => !busy && setEditingTemplate(false)} />
          <div className="relative w-full max-w-lg rounded-md border border-helm-line bg-helm-card p-5 space-y-3 max-h-[85vh] overflow-y-auto" data-testid="hr-template-modal">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-helm-fg font-medium">Onboarding template</p>
                <p className="text-[11px] text-helm-muted">Changes only affect future hires.</p>
              </div>
              <button type="button" onClick={() => setEditingTemplate(false)} className="text-helm-muted hover:text-helm-fg">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2">
              {tmplDraft.map((step, idx) => (
                <div key={step.id || idx} className="flex items-center gap-2">
                  <input
                    value={step.name}
                    onChange={(e) => {
                      const next = [...tmplDraft];
                      next[idx] = { ...next[idx], name: e.target.value };
                      setTmplDraft(next);
                    }}
                    className="flex-1 rounded-md border border-helm-line bg-helm-fg/[0.03] px-3 py-2 text-sm text-helm-fg"
                  />
                  <button type="button" disabled={idx === 0} onClick={() => moveTmplStep(idx, -1)} className="p-1 text-helm-muted hover:text-helm-fg disabled:opacity-30">
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button type="button" disabled={idx === tmplDraft.length - 1} onClick={() => moveTmplStep(idx, 1)} className="p-1 text-helm-muted hover:text-helm-fg disabled:opacity-30">
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setTmplDraft((d) => d.filter((_, i) => i !== idx))}
                    className="p-1 text-helm-status-negative hover:text-helm-status-negative"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              data-testid="hr-template-add-step"
              onClick={() => setTmplDraft((d) => [...d, { id: `hstep_new_${Date.now()}`, name: "New step", order: d.length }])}
              className="inline-flex items-center gap-1 text-xs text-helm-gold"
            >
              <Plus className="w-3.5 h-3.5" /> Add step
            </button>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setEditingTemplate(false)} className="text-sm text-helm-muted px-3 py-2">Cancel</button>
              <button
                type="button"
                disabled={busy}
                data-testid="hr-template-save"
                onClick={saveTemplate}
                className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-3 py-2 hover:bg-helm-gold-hover disabled:opacity-50"
              >
                Save template
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
