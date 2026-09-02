import { useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Sparkles, Send, CheckCircle2, Circle, AlertTriangle, Plus, Users, Lock, PenLine, Trash2, X } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const MOODS = [
  { id: "great", label: "Great" },
  { id: "good", label: "Good" },
  { id: "ok", label: "OK" },
  { id: "stressed", label: "Stressed" },
];

const NOTE_STYLES = {
  gold: "bg-[#fef9c3] text-[#422006] border-[#eab308]/40 shadow-[3px_3px_0_rgba(234,179,8,0.35)]",
  sky: "bg-[#e0f2fe] text-[#0c4a6e] border-[#38bdf8]/40 shadow-[3px_3px_0_rgba(56,189,248,0.35)]",
  emerald: "bg-[#d1fae5] text-[#064e3b] border-[#34d399]/40 shadow-[3px_3px_0_rgba(52,211,153,0.35)]",
  rose: "bg-[#ffe4e6] text-[#881337] border-[#fb7185]/40 shadow-[3px_3px_0_rgba(251,113,133,0.35)]",
  violet: "bg-[#ede9fe] text-[#4c1d95] border-[#a78bfa]/40 shadow-[3px_3px_0_rgba(167,139,250,0.35)]",
  amber: "bg-[#fef3c7] text-[#78350f] border-[#fbbf24]/40 shadow-[3px_3px_0_rgba(251,191,36,0.35)]",
};

const colStyle = {
  done: "text-emerald-400",
  in_progress: "text-gold",
  review: "text-sky-400",
  backlog: "text-zinc-500",
};

const colLabel = { backlog: "To-Do", in_progress: "in progress", review: "review", done: "done" };

export default function MyDay() {
  const { user } = useAuth();
  const { data: notesData, loading: l0, error: e0, reload: reloadNotes } = useFetch("/notes");
  const { data: mine, loading: l1, error: e1, reload: reloadMine } = useFetch("/updates/me");
  const { data: tasks, loading: l2, error: e2, reload: reloadTasks } = useFetch("/tasks/me");
  const { data: today, loading: l3, error: e3, reload: reloadToday } = useFetch("/updates/today");

  const [teamText, setTeamText] = useState("");
  const [blocker, setBlocker] = useState(false);
  const [mood, setMood] = useState("good");
  const [busy, setBusy] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const [showTask, setShowTask] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDue, setTaskDue] = useState("");
  const [taskBusy, setTaskBusy] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [noteText, setNoteText] = useState("");
  const [noteColor, setNoteColor] = useState("gold");
  const [noteBusy, setNoteBusy] = useState(false);
  const [showNoteComposer, setShowNoteComposer] = useState(false);

  if (l0 || l1 || l2 || l3) return <LoadingScreen label="Assembling your day" />;
  const dayError = e0 || e1 || e2 || e3;
  if (dayError || !notesData || !mine || !tasks || !today) {
    return (
      <ErrorScreen
        label="Could not load your day"
        message={fetchErrorMessage(dayError, "Your day view is unavailable right now.")}
        onRetry={() => { reloadNotes(); reloadMine(); reloadTasks(); reloadToday(); }}
      />
    );
  }

  const first = user?.name?.split(" ")[0] || "there";
  const hasPosted = !!mine?.update;
  const notes = notesData.notes || [];

  const saveNote = async () => {
    if (!noteText.trim()) { toast.error("Write something first"); return; }
    setNoteBusy(true);
    try {
      if (editingNote) {
        await api.patch(`/notes/${editingNote}`, { text: noteText.trim(), color: noteColor });
        toast.success("Note updated");
      } else {
        await api.post("/notes", { text: noteText.trim(), color: noteColor });
        toast.success("Private note saved");
      }
      setNoteText(""); setEditingNote(null); setShowNoteComposer(false);
      reloadNotes();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save note"); }
    finally { setNoteBusy(false); }
  };

  const startEdit = (n) => {
    setEditingNote(n.note_id);
    setNoteText(n.text);
    setNoteColor(n.color || "gold");
    setShowNoteComposer(true);
  };

  const openNewNote = () => {
    setEditingNote(null);
    setNoteText("");
    setNoteColor("gold");
    setShowNoteComposer(true);
  };

  const cancelNote = () => {
    setEditingNote(null);
    setNoteText("");
    setShowNoteComposer(false);
  };

  const delNote = async (n) => {
    try { await api.delete(`/notes/${n.note_id}`); reloadNotes(); toast.success("Note deleted"); }
    catch (e) { toast.error("Could not delete"); }
  };

  const submitTeam = async () => {
    if (!teamText.trim()) { toast.error("Write a quick update first"); return; }
    setBusy(true);
    try {
      await api.post("/updates", { text: teamText.trim(), blocker, mood });
      toast.success(hasPosted ? "Team update saved" : "Shared with your team");
      setTeamText(""); setShowTeam(false);
      reloadMine(); reloadToday();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not post"); }
    finally { setBusy(false); }
  };

  const addTask = async () => {
    if (!taskTitle.trim()) return;
    setTaskBusy(true);
    try {
      await api.post("/tasks", { title: taskTitle.trim(), tag: "Personal", column: "backlog", due: taskDue });
      toast.success("Task added");
      setTaskTitle(""); setTaskDue(""); setShowTask(false);
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
        <p className="text-zinc-400 mt-3 max-w-2xl text-base leading-relaxed">Your private notes, tasks, and optional team update — start with what matters to you.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Lock className="w-3.5 h-3.5 text-gold" />
              <SectionLabel>Notes</SectionLabel>
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 bg-white/5 rounded px-2 py-0.5">Private · only you</span>
            </div>
            <button
              data-testid="new-note-btn"
              type="button"
              onClick={openNewNote}
              className="inline-flex items-center gap-1 text-xs text-gold hover:text-gold-hover"
            >
              <Plus className="w-3.5 h-3.5" /> New note
            </button>
          </div>

          {showNoteComposer && (
            <GlassCard className="p-4 fade-up border-gold/20" data-testid="note-composer">
              <textarea
                data-testid="note-text"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                rows={3}
                placeholder="Jot a thought, reminder, or idea…"
                className="w-full rounded-lg border border-white/10 bg-[#141417] text-white text-sm p-3 focus:outline-none focus:border-gold/40 resize-none"
              />
              <div className="flex flex-wrap items-center gap-2 mt-3">
                {Object.keys(NOTE_STYLES).map((c) => (
                  <button key={c} type="button" onClick={() => setNoteColor(c)}
                    className={cn("w-6 h-6 rounded-full border-2", noteColor === c ? "border-white scale-110" : "border-transparent opacity-70")}
                    style={{ background: c === "gold" ? "#eab308" : c === "sky" ? "#38bdf8" : c === "emerald" ? "#34d399" : c === "rose" ? "#fb7185" : c === "violet" ? "#a78bfa" : "#fbbf24" }}
                    aria-label={`${c} note color`}
                  />
                ))}
                <button data-testid="save-note-btn" onClick={saveNote} disabled={noteBusy}
                  className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-gold text-black text-sm font-medium px-3 py-1.5 hover:bg-gold-hover disabled:opacity-60">
                  {noteBusy ? "Saving…" : editingNote ? "Save" : "Add note"}
                </button>
                {editingNote && (
                  <button type="button" onClick={cancelNote} className="text-xs text-zinc-500 hover:text-white">Cancel</button>
                )}
              </div>
            </GlassCard>
          )}

          {notes.length === 0 && !showNoteComposer ? (
            <EmptyState title="No private notes yet" body="Sticky notes here are only visible to you — great for priorities, reminders, and scratch ideas."
              action={<button type="button" onClick={openNewNote} className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover"><Plus className="w-4 h-4" /> Add your first note</button>} />
          ) : (
            <div className="grid sm:grid-cols-2 gap-3" data-testid="sticky-notes-grid">
              {notes.map((n) => (
                <div
                  key={n.note_id}
                  data-testid={`sticky-note-${n.note_id}`}
                  className={cn("relative rounded-sm border p-4 min-h-[120px] rotate-[-0.6deg] hover:rotate-0 transition-transform", NOTE_STYLES[n.color] || NOTE_STYLES.gold)}
                  style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                >
                  <p className="text-sm leading-relaxed pr-6 whitespace-pre-wrap">{n.text}</p>
                  <div className="absolute top-2 right-2 flex gap-1">
                    <button onClick={() => startEdit(n)} className="opacity-60 hover:opacity-100 p-0.5"><PenLine className="w-3.5 h-3.5" /></button>
                    <button onClick={() => delNote(n)} data-testid={`del-note-${n.note_id}`} className="opacity-60 hover:opacity-100 p-0.5"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <GlassCard className="p-4 fade-up">
            <button type="button" onClick={() => { setShowTeam((s) => !s); if (!showTeam && mine?.update) { setTeamText(mine.update.text || ""); setBlocker(!!mine.update.blocker); setMood(mine.update.mood || "good"); } }}
              className="flex items-center gap-2 text-sm text-zinc-300 hover:text-white w-full text-left">
              <Users className="w-4 h-4 text-gold" />
              <span>{showTeam ? "Hide team update" : "Share an update with your team (optional)"}</span>
            </button>
            {showTeam && (
              <div className="mt-3 pt-3 border-t border-white/5" data-testid="team-update-form">
                <textarea value={teamText} onChange={(e) => setTeamText(e.target.value)} rows={3}
                  placeholder="What did you move forward? Any blocker or ask?"
                  className="w-full rounded-lg border border-white/10 bg-[#141417] text-white text-sm p-3 focus:outline-none focus:border-gold/40 resize-none" />
                <div className="flex flex-wrap items-center gap-3 mt-3">
                  <div className="flex items-center gap-1.5">
                    {MOODS.map((m) => (
                      <button key={m.id} onClick={() => setMood(m.id)}
                        className={cn("text-xs rounded-full px-2.5 py-1 border transition-colors", mood === m.id ? "border-gold/40 bg-gold/10 text-white" : "border-white/10 text-zinc-400 hover:bg-white/5")}>{m.label}</button>
                    ))}
                  </div>
                  <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
                    <input type="checkbox" checked={blocker} onChange={(e) => setBlocker(e.target.checked)} className="accent-gold w-4 h-4" />
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Blocked
                  </label>
                  <button onClick={submitTeam} disabled={busy}
                    className="ml-auto inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2 hover:bg-gold-hover disabled:opacity-60">
                    {busy ? "Posting…" : "Post to team"} <Send className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </GlassCard>
        </div>

        <GlassCard className="p-5 fade-up" data-testid="team-updates-card">
          <div className="flex items-center gap-1.5 mb-4 text-gold"><Users className="w-3.5 h-3.5" /><SectionLabel>Today across the team</SectionLabel></div>
          {teamUpdates.length === 0 ? (
            <p className="text-sm text-zinc-600 py-6 text-center">No teammate updates yet today.</p>
          ) : (
            <div className="space-y-3 max-h-[320px] overflow-y-auto">
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

      <div className="mt-6">
        <div className="flex items-center justify-between mb-4">
          <SectionLabel>My tasks</SectionLabel>
          <button data-testid="myday-add-task-btn" onClick={() => setShowTask((s) => !s)}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-1.5 hover:bg-white/5">
            <Plus className="w-3.5 h-3.5" /> New task
          </button>
        </div>

        {showTask && (
          <GlassCard className="p-3 mb-3 fade-up">
            <div className="flex gap-2">
              <input data-testid="myday-task-input" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTask()} placeholder="What do you need to get done?"
                className="flex-1 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              <input data-testid="myday-task-due" type="date" value={taskDue} onChange={(e) => setTaskDue(e.target.value)}
                className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-2 py-2 focus:outline-none focus:border-gold/40" />
              <button data-testid="myday-task-save" onClick={addTask} disabled={taskBusy}
                className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover disabled:opacity-60">{taskBusy ? "…" : "Add"}</button>
            </div>
          </GlassCard>
        )}

        {myItems.length === 0 ? (
          <EmptyState icon={CheckCircle2} title="No tasks assigned to you" body="Add a personal task above, or your manager can assign work from the Tasks board." />
        ) : (
          <div className="space-y-2">
            {openItems.map((t) => (
              <GlassCard key={t.id} className="p-3 fade-up flex items-center gap-3" data-testid={`myday-task-${t.id}`}>
                <button onClick={() => moveTask(t, "done")} className="text-zinc-600 hover:text-emerald-400 shrink-0"><Circle className="w-4 h-4" /></button>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{t.title}</p>
                  <span className={cn("text-[10px] font-mono uppercase tracking-wide", colStyle[t.column])}>
                    {colLabel[t.column] || t.column.replace("_", " ")}{t.tag ? ` · ${t.tag}` : ""}
                  </span>
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
