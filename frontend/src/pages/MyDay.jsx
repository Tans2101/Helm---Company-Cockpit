import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Sparkles, Send, CheckCircle2, Circle, AlertTriangle, Plus, ArrowUpRight, Users } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { GlassCard, SectionLabel, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const MOODS = [
  { id: "great", label: "Great" },
  { id: "good", label: "Good" },
  { id: "ok", label: "OK" },
  { id: "stressed", label: "Stressed" },
];

const colStyle = {
  done: "text-emerald-400",
  in_progress: "text-gold",
  review: "text-sky-400",
  backlog: "text-zinc-500",
};

export default function MyDay() {
  const { user } = useAuth();
  const { data: mine, loading: l1, reload: reloadMine } = useFetch("/updates/me");
  const { data: tasks, loading: l2, reload: reloadTasks } = useFetch("/tasks/me");
  const { data: today, loading: l3, reload: reloadToday } = useFetch("/updates/today");

  const [text, setText] = useState("");
  const [blocker, setBlocker] = useState(false);
  const [mood, setMood] = useState("good");
  const [busy, setBusy] = useState(false);
  const [showTask, setShowTask] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskBusy, setTaskBusy] = useState(false);

  useEffect(() => {
    if (mine?.update) {
      setText(mine.update.text || "");
      setBlocker(!!mine.update.blocker);
      setMood(mine.update.mood || "good");
    }
  }, [mine]);

  if (l1 || l2 || l3) return <LoadingScreen label="Assembling your day" />;

  const first = user?.name?.split(" ")[0] || "there";
  const hasPosted = !!mine?.update;

  const submit = async () => {
    if (!text.trim()) { toast.error("Write a quick update first"); return; }
    setBusy(true);
    try {
      await api.post("/updates", { text: text.trim(), blocker, mood });
      toast.success(hasPosted ? "Update saved" : "Update posted — the CEO will see it in the briefing");
      reloadMine(); reloadToday();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not post"); }
    finally { setBusy(false); }
  };

  const addTask = async () => {
    if (!taskTitle.trim()) return;
    setTaskBusy(true);
    try {
      await api.post("/tasks", { title: taskTitle.trim(), tag: "Personal", column: "backlog" });
      toast.success("Task added");
      setTaskTitle(""); setShowTask(false);
      reloadTasks();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not add task"); }
    finally { setTaskBusy(false); }
  };

  const moveTask = async (t, column) => {
    try { await api.patch(`/tasks/${t.id}`, { column }); reloadTasks(); }
    catch (e) { toast.error("Could not update task"); }
  };

  const myItems = tasks?.items || [];
  const openItems = myItems.filter((t) => t.column !== "done");
  const doneItems = myItems.filter((t) => t.column === "done");
  const teamUpdates = (today?.updates || []).filter((u) => u.user_id !== user?.user_id);

  return (
    <div>
      <div className="mb-8 fade-up">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">My Day</p>
        <h1 className="text-3xl md:text-5xl font-light tracking-tight text-white">Morning, {first}.</h1>
        <p className="text-zinc-400 mt-3 max-w-2xl text-base leading-relaxed">Your workspace for today — work your tasks, then post one update so the whole company stays in sync.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Daily update composer */}
        <GlassCard glow className="p-5 lg:col-span-2 fade-up border-gold/20" data-testid="daily-update-card">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-gold" />
            </div>
            <div>
              <SectionLabel>Daily update</SectionLabel>
              <p className="text-xs text-zinc-500 mt-0.5">{hasPosted ? "Posted today — edit anytime." : "One update, once a day."}</p>
            </div>
          </div>
          <textarea data-testid="update-text" value={text} onChange={(e) => setText(e.target.value)} rows={4}
            placeholder="What did you move forward? Any blocker or ask?"
            className="w-full rounded-lg border border-white/10 bg-[#141417] text-white text-sm p-3 focus:outline-none focus:border-gold/40 resize-none placeholder:text-zinc-600" />
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <div className="flex items-center gap-1.5">
              {MOODS.map((m) => (
                <button key={m.id} data-testid={`mood-${m.id}`} onClick={() => setMood(m.id)}
                  className={cn("text-xs rounded-full px-2.5 py-1 border transition-colors", mood === m.id ? "border-gold/40 bg-gold/10 text-white" : "border-white/10 text-zinc-400 hover:bg-white/5")}>{m.label}</button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-300 ml-auto cursor-pointer">
              <input data-testid="update-blocker" type="checkbox" checked={blocker} onChange={(e) => setBlocker(e.target.checked)} className="accent-gold w-4 h-4" />
              <span className="flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> I'm blocked</span>
            </label>
            <button data-testid="submit-update-btn" onClick={submit} disabled={busy}
              className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2 transition-colors hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Saving…" : hasPosted ? "Save update" : "Post update"} <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </GlassCard>

        {/* Team signals */}
        <GlassCard className="p-5 fade-up" data-testid="team-updates-card">
          <div className="flex items-center gap-1.5 mb-4 text-gold"><Users className="w-3.5 h-3.5" /><SectionLabel>Today across the team</SectionLabel></div>
          {teamUpdates.length === 0 ? (
            <p className="text-sm text-zinc-600 py-6 text-center">No teammate updates yet today.</p>
          ) : (
            <div className="space-y-3 max-h-[280px] overflow-y-auto">
              {teamUpdates.map((u) => (
                <div key={u.update_id} className="text-sm" data-testid={`team-update-${u.update_id}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-white text-xs font-medium">{u.user_name}</span>
                    {u.blocker && <span className="text-[10px] text-amber-400 bg-amber-400/10 rounded px-1.5 py-0.5 font-mono uppercase">Blocked</span>}
                    <span className="text-[10px] text-zinc-600 ml-auto font-mono">{u.ago}</span>
                  </div>
                  <p className="text-zinc-400 text-xs mt-1 leading-relaxed">{u.text}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      {/* My tasks */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-4">
          <SectionLabel>My tasks</SectionLabel>
          <button data-testid="myday-add-task-btn" onClick={() => setShowTask((s) => !s)}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-1.5 transition-colors hover:bg-white/5">
            <Plus className="w-3.5 h-3.5" /> New task
          </button>
        </div>

        {showTask && (
          <GlassCard className="p-3 mb-3 fade-up">
            <div className="flex gap-2">
              <input data-testid="myday-task-input" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTask()} placeholder="What do you need to get done?"
                className="flex-1 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40 placeholder:text-zinc-600" />
              <button data-testid="myday-task-save" onClick={addTask} disabled={taskBusy}
                className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover disabled:opacity-60">{taskBusy ? "…" : "Add"}</button>
            </div>
          </GlassCard>
        )}

        {myItems.length === 0 ? (
          <EmptyState icon={CheckCircle2} title="No tasks assigned to you" body="Add a personal task above, or your manager can assign work to you from the Tasks board." />
        ) : (
          <div className="space-y-2">
            {openItems.map((t) => (
              <GlassCard key={t.id} className="p-3 fade-up flex items-center gap-3" data-testid={`myday-task-${t.id}`}>
                <button onClick={() => moveTask(t, "done")} data-testid={`myday-task-done-${t.id}`} className="text-zinc-600 hover:text-emerald-400 transition-colors shrink-0">
                  <Circle className="w-4 h-4" />
                </button>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{t.title}</p>
                  <span className={cn("text-[10px] font-mono uppercase tracking-wide", colStyle[t.column])}>{t.column.replace("_", " ")}{t.tag ? ` · ${t.tag}` : ""}</span>
                </div>
                {t.due && <span className="text-[11px] font-mono text-zinc-600 shrink-0">{t.due}</span>}
              </GlassCard>
            ))}
            {doneItems.map((t) => (
              <GlassCard key={t.id} className="p-3 flex items-center gap-3 opacity-60" data-testid={`myday-task-${t.id}`}>
                <button onClick={() => moveTask(t, "in_progress")} className="text-emerald-400 shrink-0"><CheckCircle2 className="w-4 h-4" /></button>
                <p className="text-sm text-zinc-500 line-through truncate flex-1">{t.title}</p>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
