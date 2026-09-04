import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, X, Scale, FileText, Upload } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import {
  PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState,
} from "@/components/kit";
import { cn } from "@/lib/utils";

const STATUS_META = {
  draft: { label: "Draft", className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30" },
  internal_review: { label: "Internal review", className: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  counterparty_review: { label: "Counterparty review", className: "bg-amber-500/15 text-amber-200 border-amber-500/30" },
  signed: { label: "Signed", className: "bg-violet-500/15 text-violet-200 border-violet-500/30" },
  filed: { label: "Filed", className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
};

const MEMBER_STATUSES = new Set(["draft", "internal_review"]);
const LEAD_STATUSES = ["draft", "internal_review", "counterparty_review", "signed", "filed"];

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.draft;
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

export default function Legal() {
  const { data, loading, error, reload } = useFetch("/legal/matters");
  const { data: membersData } = useFetch("/members");
  const [showFiled, setShowFiled] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ title: "", matter_type: "contract", assigned_to: "", notes: "" });
  const fileRef = useRef(null);

  const allMatters = useMemo(() => data?.matters || [], [data?.matters]);
  const visible = useMemo(
    () => (showFiled ? allMatters : allMatters.filter((m) => m.status !== "filed")),
    [allMatters, showFiled],
  );
  const selected = useMemo(
    () => allMatters.find((m) => m.id === selectedId) || null,
    [allMatters, selectedId],
  );
  const workspaceMembers = (membersData?.members || []).filter((m) => m.user_id && m.status === "active");

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      return;
    }
    setDraft({
      title: selected.title || "",
      matter_type: selected.matter_type || "contract",
      assigned_to: selected.assigned_to || "",
      notes: selected.notes || "",
      status: selected.status || "draft",
    });
  }, [selected]);

  if (loading) return <LoadingScreen label="Loading legal matters" />;
  if (error) {
    const status = error?.response?.status;
    if (status === 403) {
      return (
        <ErrorScreen
          label="Access denied"
          message="You are not a member of Legal. Ask your CEO to add you."
          onRetry={reload}
        />
      );
    }
    if (status === 404) {
      return (
        <ErrorScreen
          label="Legal not enabled"
          message="Enable Legal under Settings → Departments first."
          onRetry={reload}
        />
      );
    }
    return (
      <ErrorScreen
        label="Could not load Legal"
        message={fetchErrorMessage(error, "Legal data is unavailable.")}
        onRetry={reload}
      />
    );
  }

  const isLead = Boolean(data?.is_lead || data?.can_reassign);
  const myId = data?.my_user_id;
  const isAssignee = selected && selected.assigned_to === myId;
  const canEdit = Boolean(selected && (isLead || isAssignee));
  const statusOptions = isLead ? LEAD_STATUSES : ["draft", "internal_review"];

  const createMatter = async () => {
    if (!form.title.trim()) {
      toast.error("Title is required");
      return;
    }
    setBusy(true);
    try {
      const body = {
        title: form.title.trim(),
        matter_type: form.matter_type,
        notes: form.notes.trim(),
      };
      if (form.assigned_to) body.assigned_to = form.assigned_to;
      const { data: res } = await api.post("/legal/matters", body);
      toast.success("Matter created");
      setForm({ title: "", matter_type: "contract", assigned_to: "", notes: "" });
      setAdding(false);
      await reload();
      if (res?.matter?.id) setSelectedId(res.matter.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create matter");
    } finally {
      setBusy(false);
    }
  };

  const saveMatter = async () => {
    if (!selected || !draft) return;
    const body = {};
    if (canEdit) {
      body.title = draft.title.trim();
      body.matter_type = draft.matter_type;
      body.notes = draft.notes;
      body.status = draft.status;
    }
    if (isLead && draft.assigned_to !== selected.assigned_to) {
      body.assigned_to = draft.assigned_to || null;
    }
    if (!isLead && !MEMBER_STATUSES.has(draft.status)) {
      toast.error("Only a lead or CEO can advance past internal review");
      return;
    }
    setBusy(true);
    try {
      const { data: res } = await api.patch(`/legal/matters/${selected.id}`, body);
      toast.success("Matter updated");
      await reload();
      if (res?.matter?.id) setSelectedId(res.matter.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update matter");
    } finally {
      setBusy(false);
    }
  };

  const uploadDocument = async (file) => {
    if (!selected || !file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data: res } = await api.post(`/legal/matters/${selected.id}/document`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Document attached");
      await reload();
      if (res?.matter?.id) setSelectedId(res.matter.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not upload document");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const viewDocument = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const { data: res } = await api.get(`/legal/matters/${selected.id}/document`);
      if (res?.presigned_url) {
        window.open(res.presigned_url, "_blank", "noopener,noreferrer");
      } else {
        toast.error("No download URL available");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not open document");
    } finally {
      setBusy(false);
    }
  };

  const deleteMatter = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete matter “${selected.title}”?`)) return;
    setBusy(true);
    try {
      await api.delete(`/legal/matters/${selected.id}`);
      toast.success("Matter deleted");
      setSelectedId(null);
      await reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="legal-page">
      <PageHeader
        title={data?.name || "Legal"}
        subtitle="Matter queue — contracts and reviews moving independently."
        action={(
          <button
            type="button"
            data-testid="add-legal-matter-btn"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover"
          >
            <Plus className="w-4 h-4" /> New matter
          </button>
        )}
      />

      <div className="flex items-center justify-between gap-3 mb-4">
        <p className="text-xs text-zinc-500 font-mono">
          {visible.length} shown · {allMatters.length} total
        </p>
        <label className="inline-flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            data-testid="legal-show-filed"
            checked={showFiled}
            onChange={(e) => setShowFiled(e.target.checked)}
            className="rounded border-white/20 bg-transparent"
          />
          Show filed
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Scale}
          title={allMatters.length ? "No open matters" : "No matters yet"}
          body={
            allMatters.length
              ? "Turn on “Show filed” to see closed matters, or create a new one."
              : "Create a matter to track contracts, compliance, and reviews."
          }
          action={(
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"
            >
              <Plus className="w-4 h-4" /> New matter
            </button>
          )}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border border-white/10 mb-6">
          <table className="w-full text-left text-sm" data-testid="legal-table">
            <thead>
              <tr className="border-b border-white/10 text-[10px] font-mono uppercase tracking-wide text-zinc-500">
                <th className="px-3 py-2 font-medium">Title</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Assignee</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Doc</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((m) => (
                <tr
                  key={m.id}
                  data-testid={`legal-row-${m.id}`}
                  onClick={() => setSelectedId(m.id)}
                  className={cn(
                    "border-b border-white/5 cursor-pointer transition-colors hover:bg-white/[0.03]",
                    selectedId === m.id && "bg-gold/[0.06]",
                  )}
                >
                  <td className="px-3 py-2.5 text-white truncate max-w-[16rem]">{m.title}</td>
                  <td className="px-3 py-2.5 text-zinc-400 capitalize">{m.matter_type || "—"}</td>
                  <td className="px-3 py-2.5 text-zinc-400 truncate max-w-[10rem]">{personLabel(m.assignee)}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={m.status} /></td>
                  <td className="px-3 py-2.5 text-zinc-500">
                    {m.has_document ? <FileText className="w-3.5 h-3.5 text-gold" /> : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && draft && (
        <GlassCard className="p-5 space-y-4" data-testid="legal-detail">
          <div className="flex items-start justify-between gap-3">
            <div>
              <SectionLabel>Matter detail</SectionLabel>
              <p className="text-white text-sm mt-1">{selected.title}</p>
            </div>
            <button type="button" onClick={() => setSelectedId(null)} className="text-zinc-500 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Title</span>
              <input
                data-testid="legal-edit-title"
                disabled={!canEdit || busy}
                value={draft.title}
                onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Type</span>
              <select
                data-testid="legal-edit-type"
                disabled={!canEdit || busy}
                value={draft.matter_type}
                onChange={(e) => setDraft((d) => ({ ...d, matter_type: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                {(data?.matter_types || ["contract", "compliance", "other"]).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Status</span>
              <select
                data-testid="legal-edit-status"
                disabled={!canEdit || busy}
                value={draft.status}
                onChange={(e) => setDraft((d) => ({ ...d, status: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                {statusOptions.map((s) => (
                  <option key={s} value={s}>{STATUS_META[s]?.label || s}</option>
                ))}
                {!isLead && LEAD_STATUSES.filter((s) => !MEMBER_STATUSES.has(s)).includes(selected.status) && (
                  <option value={selected.status}>{STATUS_META[selected.status]?.label}</option>
                )}
              </select>
            </label>
            <label className="space-y-1 md:col-span-2">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Assignee</span>
              <select
                data-testid="legal-edit-assignee"
                disabled={!isLead || busy}
                value={draft.assigned_to || ""}
                onChange={(e) => setDraft((d) => ({ ...d, assigned_to: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                <option value="">Unassigned</option>
                {workspaceMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
                ))}
              </select>
              {!isLead && (
                <span className="text-[10px] text-zinc-600">Only a lead or CEO can reassign</span>
              )}
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Notes</span>
            <textarea
              data-testid="legal-edit-notes"
              disabled={!canEdit || busy}
              value={draft.notes}
              onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
              rows={3}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white disabled:opacity-50"
            />
          </label>

          <div className="rounded-md border border-white/10 bg-white/[0.02] p-3 space-y-2">
            <p className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Document</p>
            {selected.has_document ? (
              <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-300">
                <FileText className="w-4 h-4 text-gold shrink-0" />
                <span className="truncate">{selected.document?.filename || "Attached file"}</span>
                <button
                  type="button"
                  disabled={busy}
                  data-testid="legal-view-doc"
                  onClick={viewDocument}
                  className="text-xs text-gold hover:underline disabled:opacity-50"
                >
                  View / download
                </button>
              </div>
            ) : (
              <p className="text-xs text-zinc-600">No document attached yet.</p>
            )}
            {canEdit && (
              <div>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,image/png,image/jpeg,application/pdf"
                  className="hidden"
                  data-testid="legal-doc-input"
                  onChange={(e) => uploadDocument(e.target.files?.[0])}
                />
                <button
                  type="button"
                  disabled={busy}
                  data-testid="legal-upload-doc"
                  onClick={() => fileRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-md border border-white/15 text-zinc-300 text-sm px-3 py-1.5 hover:bg-white/5 disabled:opacity-50"
                >
                  <Upload className="w-3.5 h-3.5" />
                  {selected.has_document ? "Replace document" : "Attach document"}
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
            <span>Created by: <span className="text-zinc-300">{personLabel(selected.creator)}</span></span>
            <span>Status: <StatusBadge status={selected.status} /></span>
          </div>

          <div className="flex flex-wrap gap-2">
            {canEdit && (
              <button
                type="button"
                disabled={busy}
                data-testid="legal-save-btn"
                onClick={saveMatter}
                className="rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
              >
                Save changes
              </button>
            )}
            {isLead && (
              <button
                type="button"
                disabled={busy}
                data-testid="legal-delete-btn"
                onClick={deleteMatter}
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
          <div className="relative w-full max-w-md rounded-md border border-white/10 bg-[#141417] p-5 space-y-3" data-testid="legal-create-modal">
            <div className="flex items-center justify-between">
              <p className="text-sm text-white font-medium">New legal matter</p>
              <button type="button" onClick={() => setAdding(false)} className="text-zinc-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Title</span>
              <input
                data-testid="legal-new-title"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="NDA — Acme Supplier"
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                autoFocus
              />
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Type</span>
              <select
                data-testid="legal-new-type"
                value={form.matter_type}
                onChange={(e) => setForm((f) => ({ ...f, matter_type: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              >
                {(data?.matter_types || ["contract", "compliance", "other"]).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Assignee</span>
              <select
                data-testid="legal-new-assignee"
                value={form.assigned_to}
                onChange={(e) => setForm((f) => ({ ...f, assigned_to: e.target.value }))}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              >
                <option value="">Me (default)</option>
                {workspaceMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-500">Notes</span>
              <textarea
                data-testid="legal-new-notes"
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
                data-testid="legal-create-submit"
                onClick={createMatter}
                className="rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
              >
                Create matter
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
