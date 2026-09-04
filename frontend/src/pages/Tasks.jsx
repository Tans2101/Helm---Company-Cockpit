import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { GripVertical, Plus, X } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const priorityStyle = {
  High: "text-rose-400 bg-rose-400/10",
  Medium: "text-amber-400 bg-amber-400/10",
  Low: "text-zinc-400 bg-white/5",
};

const emptyTask = () => ({ title: "", priority: "Medium", tag: "General", due: "", assignee_user_id: "" });

export default function Tasks() {
  const { data, loading, error, reload, setData } = useFetch("/tasks");
  const { data: membersData } = useFetch("/members");
  const [searchParams] = useSearchParams();
  const focusTaskId = searchParams.get("task") || "";
  const [dragId, setDragId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyTask());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!focusTaskId || !data?.items?.length) return;
    const el = document.querySelector(`[data-testid="task-${focusTaskId}"]`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusTaskId, data?.items]);

  if (loading) return <LoadingScreen label="Loading board" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load board"
        message={fetchErrorMessage(error, "Task board is unavailable right now.")}
        onRetry={reload}
      />
    );
  }

  const canCreate = data.can_create;
  const canAssign = data.can_assign;
  // Exclude self — "Myself" is already the empty default option
  const assignableMembers = (membersData?.members || []).filter(
    (m) => m.user_id && m.status === "active" && !m.is_self && m.user_id !== data.my_user_id,
  );

  const move = async (taskId, column) => {
    let snapshot = null;
    setData((prev) => {
      if (!prev) return prev;
      snapshot = prev;
      return {
        ...prev,
        items: prev.items.map((t) => (t.id === taskId ? { ...t, column } : t)),
      };
    });
    try {
      await api.patch(`/tasks/${taskId}`, { column });
    } catch (e) {
      if (snapshot) setData(snapshot);
      toast.error(e?.response?.data?.detail || "Failed to move task");
    }
  };

  const onDrop = (col) => {
    if (dragId) { move(dragId, col); setDragId(null); }
  };

  const submit = async () => {
    if (!form.title.trim()) { toast.error("Add a title"); return; }
    setBusy(true);
    try {
      const payload = { title: form.title.trim(), priority: form.priority, tag: form.tag, due: form.due };
      if (canAssign && form.assignee_user_id) payload.assignee_user_id = form.assignee_user_id;
      await api.post("/tasks", payload);
      toast.success("Task created");
      setForm(emptyTask());
      setShowForm(false);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not create"); }
    finally { setBusy(false); }
  };

  const action = canCreate ? (
    <button data-testid="new-task-btn" onClick={() => { setForm(emptyTask()); setShowForm(true); }}
      className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 transition-colors hover:bg-gold-hover">
      <Plus className="w-4 h-4" /> New task
    </button>
  ) : null;

  const board = (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {data.columns.map((col) => {
        const items = data.items.filter((t) => t.column === col.id);
        return (
          <div key={col.id}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(col.id)}
            data-testid={`column-${col.id}`}
            className="rounded-xl border border-white/5 bg-white/[0.015] p-3 min-h-[200px]">
            <div className="flex items-center justify-between px-1 mb-3">
              <span className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-400">{col.name}</span>
              <span className="font-mono text-xs text-zinc-600">{items.length}</span>
            </div>
            <div className="space-y-2">
              {items.map((t) => {
                const mine = t.assignee_user_id === data.my_user_id;
                return (
                <div key={t.id}
                  draggable
                  onDragStart={() => setDragId(t.id)}
                  data-testid={`task-${t.id}`}
                  className={cn(
                    "group rounded-lg border border-white/5 bg-[#141417] p-3 cursor-grab active:cursor-grabbing transition-colors hover:border-gold/30",
                    mine && "border-l-2 border-l-gold/60",
                    focusTaskId === t.id && "ring-1 ring-gold/50 border-gold/40",
                  )}>
                  <div className="flex items-start gap-2">
                    <GripVertical className="w-3.5 h-3.5 text-zinc-700 mt-0.5 group-hover:text-zinc-500" />
                    <div className="flex-1">
                      <p className="text-sm text-white leading-snug">{t.title}</p>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <span className={cn("text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5", priorityStyle[t.priority])}>{t.priority}</span>
                        <span className="text-[10px] font-mono text-zinc-600">{t.tag}</span>
                        {t.due && <span className="text-[10px] font-mono text-zinc-600 ml-auto">{t.due}</span>}
                      </div>
                      {t.progress > 0 && t.progress < 100 && (
                        <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                          <div className="h-full bg-gold/70 rounded-full" style={{ width: `${t.progress}%` }} />
                        </div>
                      )}
                      <div className="flex items-center gap-1.5 mt-2">
                        <span className="w-4 h-4 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center text-[9px] text-gold">{(t.assignee || "?")[0]}</span>
                        <span className="text-[11px] text-zinc-500">{t.assignee}{mine && " · you"}</span>
                      </div>
                    </div>
                  </div>
                </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div>
      <PageHeader title="Tasks" subtitle="Delegate, track and sync work across your team. Drag cards across the board — your tasks are marked in gold." action={action} />
      {data.items.length === 0 ? (
        <EmptyState title="No tasks yet" body="Create the first task, or assign work to a teammate."
          action={canCreate ? <button data-testid="empty-new-task-btn" onClick={() => { setForm(emptyTask()); setShowForm(true); }} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> New task</button> : null} />
      ) : board}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="task-form">
            <div className="flex items-center justify-between mb-5"><h3 className="text-lg text-white font-light">New task</h3><button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button></div>
            <label className="text-xs text-zinc-500 block">Title
              <input data-testid="task-title" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="What needs doing?" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
            </label>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <label className="text-xs text-zinc-500">Priority
                <select data-testid="task-priority" value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40">
                  {["High", "Medium", "Low"].map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>
              <label className="text-xs text-zinc-500">Due date
                <input data-testid="task-due" type="date" value={form.due} onChange={(e) => setForm((f) => ({ ...f, due: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <label className="text-xs text-zinc-500 col-span-2">Tag
                <input data-testid="task-tag" value={form.tag} onChange={(e) => setForm((f) => ({ ...f, tag: e.target.value }))} placeholder="Growth" className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              {canAssign && (
                <label className="text-xs text-zinc-500 col-span-2">Assign to
                  <select data-testid="task-assignee" value={form.assignee_user_id} onChange={(e) => setForm((f) => ({ ...f, assignee_user_id: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40">
                    <option value="">Myself</option>
                    {assignableMembers.map((m) => <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>)}
                  </select>
                </label>
              )}
            </div>
            <button data-testid="save-task-btn" onClick={submit} disabled={busy} className="mt-5 w-full rounded-md bg-gold text-black font-medium py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">{busy ? "Creating…" : "Create task"}</button>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
