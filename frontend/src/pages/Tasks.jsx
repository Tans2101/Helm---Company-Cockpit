import { useState } from "react";
import { toast } from "sonner";
import { GripVertical } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const priorityStyle = {
  High: "text-rose-400 bg-rose-400/10",
  Medium: "text-amber-400 bg-amber-400/10",
  Low: "text-zinc-400 bg-white/5",
};

export default function Tasks() {
  const { data, loading, setData } = useFetch("/tasks");
  const [dragId, setDragId] = useState(null);

  if (loading || !data) return <LoadingScreen label="Loading board" />;
  if (data.items.length === 0) return <div><PageHeader title="Tasks" subtitle="Delegate, track and sync work across your team." /><EmptyState title="No tasks yet" body="Delegated work and follow-ups will appear on your board here." /></div>;

  const move = async (taskId, column) => {
    const items = data.items.map((t) => (t.id === taskId ? { ...t, column } : t));
    setData({ ...data, items });
    try {
      await api.patch(`/tasks/${taskId}`, { column });
    } catch (e) {
      toast.error("Failed to move task");
    }
  };

  const onDrop = (col) => {
    if (dragId) {
      move(dragId, col);
      setDragId(null);
    }
  };

  return (
    <div>
      <PageHeader title="Tasks" subtitle="Delegate, track and sync. Drag cards across the board — GitHub sync available on Pro." />
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
                {items.map((t) => (
                  <div key={t.id}
                    draggable
                    onDragStart={() => setDragId(t.id)}
                    data-testid={`task-${t.id}`}
                    className="group rounded-lg border border-white/5 bg-[#141417] p-3 cursor-grab active:cursor-grabbing transition-colors hover:border-gold/30">
                    <div className="flex items-start gap-2">
                      <GripVertical className="w-3.5 h-3.5 text-zinc-700 mt-0.5 group-hover:text-zinc-500" />
                      <div className="flex-1">
                        <p className="text-sm text-white leading-snug">{t.title}</p>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          <span className={cn("text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5", priorityStyle[t.priority])}>{t.priority}</span>
                          <span className="text-[10px] font-mono text-zinc-600">{t.tag}</span>
                          <span className="text-[10px] font-mono text-zinc-600 ml-auto">{t.due}</span>
                        </div>
                        {t.progress > 0 && t.progress < 100 && (
                          <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                            <div className="h-full bg-gold/70 rounded-full" style={{ width: `${t.progress}%` }} />
                          </div>
                        )}
                        <div className="flex items-center gap-1.5 mt-2">
                          <span className="w-4 h-4 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center text-[9px] text-gold">{t.assignee[0]}</span>
                          <span className="text-[11px] text-zinc-500">{t.assignee}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
