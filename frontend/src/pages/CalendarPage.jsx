import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  ChevronLeft, ChevronRight, CalendarPlus, Clock, Users, Plus, X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { LoadingScreen, ErrorScreen, EmptyState, GlassCard } from "@/components/kit";
import { cn } from "@/lib/utils";

const HOUR_HEIGHT = 52;
const GRID_START = 7;
const GRID_END = 20;
const DAY_LABELS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

const typeBlock = {
  Sales: "bg-gold/25 border-gold/40 text-gold",
  Internal: "bg-sky-500/20 border-sky-400/35 text-sky-200",
  "1:1": "bg-emerald-500/20 border-emerald-400/35 text-emerald-200",
  Board: "bg-violet-500/20 border-violet-400/35 text-violet-200",
  Decision: "bg-rose-500/15 border-rose-400/30 text-rose-200",
  Task: "bg-amber-500/15 border-amber-400/30 text-amber-200",
  Deadline: "bg-amber-500/15 border-amber-400/30 text-amber-200",
};

const typeDot = {
  Sales: "bg-gold",
  Internal: "bg-sky-400",
  "1:1": "bg-emerald-400",
  Board: "bg-violet-400",
  Decision: "bg-rose-400",
  Task: "bg-amber-400",
  Deadline: "bg-amber-400",
};

function pad(n) {
  return String(n).padStart(2, "0");
}

function toIsoDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function startOfWeek(d) {
  const copy = new Date(d);
  copy.setHours(0, 0, 0, 0);
  copy.setDate(copy.getDate() - copy.getDay());
  return copy;
}

function addDays(d, n) {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function parseEventStart(ev) {
  if (ev.start_at) return new Date(ev.start_at);
  if (ev.date && ev.time) return new Date(`${ev.date}T${ev.time}:00`);
  if (ev.date) return new Date(`${ev.date}T00:00:00`);
  return null;
}

function weekNumber(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

function formatAgendaDay(d, today) {
  const tomorrow = addDays(today, 1);
  if (sameDay(d, today)) return `TODAY · ${d.toLocaleDateString(undefined, { month: "numeric", day: "numeric", year: "2-digit" })}`;
  if (sameDay(d, tomorrow)) return `TOMORROW · ${d.toLocaleDateString(undefined, { month: "numeric", day: "numeric", year: "2-digit" })}`;
  return d.toLocaleDateString(undefined, { weekday: "long", month: "numeric", day: "numeric" }).toUpperCase();
}

function MiniMonth({ month, selected, weekDays, onSelectDay, onPrev, onNext }) {
  const year = month.getFullYear();
  const m = month.getMonth();
  const first = new Date(year, m, 1);
  const startPad = first.getDay();
  const daysInMonth = new Date(year, m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startPad; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, m, d));

  return (
    <div className="px-4 pt-4 pb-3 border-b border-white/5">
      <div className="flex items-center justify-between mb-3">
        <button type="button" onClick={onPrev} className="p-1 text-zinc-500 hover:text-white rounded" aria-label="Previous month">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <p className="text-sm font-medium text-white">
          {month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
        </p>
        <button type="button" onClick={onNext} className="p-1 text-zinc-500 hover:text-white rounded" aria-label="Next month">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center mb-1">
        {DAY_LABELS.map((l) => (
          <span key={l} className="text-[9px] font-mono text-zinc-600">{l[0]}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((day, i) => {
          if (!day) return <span key={`e-${i}`} />;
          const iso = toIsoDate(day);
          const inWeek = weekDays.some((wd) => sameDay(wd, day));
          const isSelected = sameDay(day, selected);
          const isToday = sameDay(day, new Date());
          return (
            <button
              key={iso}
              type="button"
              onClick={() => onSelectDay(day)}
              className={cn(
                "relative h-7 rounded text-xs font-mono transition-colors",
                inWeek && !isSelected && "bg-white/[0.04]",
                isSelected ? "bg-gold text-black font-semibold" : "text-zinc-400 hover:text-white",
                isToday && !isSelected && "ring-1 ring-gold/50",
              )}
            >
              {day.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AgendaSidebar({ events, weekDays, selectedDay, onSelectDay }) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const grouped = useMemo(() => {
    const map = new Map();
    weekDays.forEach((d) => map.set(toIsoDate(d), []));
    events.forEach((ev) => {
      const key = ev.date || (ev.start_at ? toIsoDate(new Date(ev.start_at)) : null);
      if (key && map.has(key)) map.get(key).push(ev);
    });
    for (const [, list] of map) {
      list.sort((a, b) => {
        if (a.all_day && !b.all_day) return -1;
        if (!a.all_day && b.all_day) return 1;
        return (parseEventStart(a)?.getTime() || 0) - (parseEventStart(b)?.getTime() || 0);
      });
    }
    return weekDays.map((d) => ({ day: d, items: map.get(toIsoDate(d)) || [] }));
  }, [events, weekDays]);

  return (
    <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4 min-h-0">
      {grouped.map(({ day, items }) => (
        <div key={toIsoDate(day)}>
          <button
            type="button"
            onClick={() => onSelectDay(day)}
            className={cn(
              "w-full text-left text-[10px] font-mono uppercase tracking-[0.15em] mb-2 px-1",
              sameDay(day, selectedDay) ? "text-gold" : "text-zinc-500 hover:text-zinc-300",
            )}
          >
            {formatAgendaDay(day, today)}
          </button>
          {items.length === 0 ? (
            <p className="text-xs text-zinc-700 px-1 py-1">No events</p>
          ) : (
            <div className="space-y-1">
              {items.map((ev) => (
                <button
                  key={ev.id}
                  type="button"
                  onClick={() => onSelectDay(day)}
                  className="w-full flex items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-white/[0.04] transition-colors"
                  data-testid={`agenda-${ev.id}`}
                >
                  <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", typeDot[ev.type] || "bg-zinc-500")} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-zinc-200 truncate">{ev.title}</p>
                    <p className="text-[11px] text-zinc-500">
                      {ev.all_day ? "All day" : `${ev.time || "—"} · ${ev.duration || 0}m`}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function WeekGrid({ weekDays, events, selectedDay, onEventClick }) {
  const now = new Date();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const hours = [];
  for (let h = GRID_START; h <= GRID_END; h++) hours.push(h);

  const byDay = useMemo(() => {
    const map = weekDays.map((d) => ({ day: d, timed: [], allDay: [] }));
    events.forEach((ev) => {
      const start = parseEventStart(ev);
      if (!start) return;
      const idx = weekDays.findIndex((d) => sameDay(d, start));
      if (idx < 0) return;
      if (ev.all_day) map[idx].allDay.push(ev);
      else map[idx].timed.push(ev);
    });
    return map;
  }, [events, weekDays]);

  const nowTop = ((now.getHours() + now.getMinutes() / 60) - GRID_START) * HOUR_HEIGHT;
  const showNowLine = now.getHours() >= GRID_START && now.getHours() <= GRID_END;

  return (
    <div className="flex-1 flex flex-col min-h-0 min-w-0">
      {/* Day headers */}
      <div className="grid border-b border-white/10 shrink-0" style={{ gridTemplateColumns: "52px repeat(7, 1fr)" }}>
        <div className="px-2 py-2 text-[10px] font-mono text-zinc-600 border-r border-white/5">
          CW {weekNumber(weekDays[0])}
        </div>
        {weekDays.map((d) => {
          const isToday = sameDay(d, today);
          const isSelected = sameDay(d, selectedDay);
          return (
            <div
              key={toIsoDate(d)}
              className={cn(
                "px-2 py-2 text-center border-r border-white/5 last:border-r-0",
                isSelected && "bg-gold/[0.06]",
              )}
            >
              <p className="text-[10px] font-mono text-zinc-500">{DAY_LABELS[d.getDay()]}</p>
              <p className={cn(
                "inline-flex items-center justify-center w-8 h-8 mt-0.5 rounded-full font-mono text-lg",
                isToday ? "bg-gold text-black font-semibold" : "text-white",
              )}>
                {d.getDate()}
              </p>
            </div>
          );
        })}
      </div>

      {/* All-day row */}
      <div className="grid border-b border-white/10 shrink-0 min-h-[36px]" style={{ gridTemplateColumns: "52px repeat(7, 1fr)" }}>
        <div className="px-2 py-1 text-[9px] font-mono text-zinc-600 border-r border-white/5 flex items-center">all-day</div>
        {byDay.map(({ day, allDay }) => (
          <div key={toIsoDate(day)} className="px-1 py-1 border-r border-white/5 last:border-r-0 flex flex-col gap-0.5">
            {allDay.map((ev) => (
              <button
                key={ev.id}
                type="button"
                onClick={() => onEventClick?.(ev)}
                className={cn("rounded px-1.5 py-0.5 text-[10px] truncate border text-left w-full", typeBlock[ev.type] || "bg-white/10 border-white/10 text-zinc-300", ev.source === "helm" && "cursor-pointer hover:brightness-110")}
                title={ev.title}
              >
                {ev.title}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Time grid */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="grid relative" style={{ gridTemplateColumns: "52px repeat(7, 1fr)", minHeight: (GRID_END - GRID_START + 1) * HOUR_HEIGHT }}>
          {/* Hour labels */}
          <div className="border-r border-white/5 relative">
            {hours.map((h) => (
              <div
                key={h}
                className="absolute left-0 right-0 pr-2 text-right text-[10px] font-mono text-zinc-600 -translate-y-2"
                style={{ top: (h - GRID_START) * HOUR_HEIGHT }}
              >
                {h === 12 ? "noon" : h < 12 ? `${h} AM` : `${h - 12} PM`}
              </div>
            ))}
          </div>

          {/* Day columns */}
          {byDay.map(({ day, timed }, colIdx) => {
            const isToday = sameDay(day, today);
            return (
              <div
                key={toIsoDate(day)}
                className={cn(
                  "relative border-r border-white/5 last:border-r-0",
                  sameDay(day, selectedDay) && "bg-gold/[0.03]",
                )}
              >
                {hours.map((h) => (
                  <div
                    key={h}
                    className="border-b border-white/[0.04]"
                    style={{ height: HOUR_HEIGHT }}
                  />
                ))}

                {isToday && showNowLine && (
                  <div className="absolute left-0 right-0 z-20 pointer-events-none flex items-center" style={{ top: nowTop }}>
                    <span className="absolute -left-[52px] w-[48px] text-right text-[9px] font-mono text-rose-400 pr-1">
                      {now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                    </span>
                    <div className="flex-1 h-px bg-rose-500" />
                    <div className="w-2 h-2 rounded-full bg-rose-500 -ml-1" />
                  </div>
                )}

                {timed.map((ev) => {
                  const start = parseEventStart(ev);
                  if (!start) return null;
                  const startFrac = start.getHours() + start.getMinutes() / 60;
                  const durH = (ev.duration || 30) / 60;
                  const top = (startFrac - GRID_START) * HOUR_HEIGHT;
                  const height = Math.max(durH * HOUR_HEIGHT - 2, 22);
                  if (startFrac < GRID_START || startFrac > GRID_END) return null;
                  return (
                    <button
                      key={ev.id}
                      type="button"
                      data-testid={`meeting-${ev.id}`}
                      onClick={() => onEventClick?.(ev)}
                      className={cn(
                        "absolute left-1 right-1 z-10 rounded-md border px-1.5 py-1 overflow-hidden text-left shadow-sm",
                        typeBlock[ev.type] || "bg-white/10 border-white/15 text-zinc-200",
                        ev.source === "helm" && "cursor-pointer hover:brightness-110",
                      )}
                      style={{ top: top + 1, height }}
                      title={ev.title}
                    >
                      <p className="text-[11px] font-medium leading-tight truncate">{ev.title}</p>
                      <p className="text-[10px] opacity-80 truncate">
                        {ev.time}{ev.duration ? ` · ${ev.duration}m` : ""}
                      </p>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const navigate = useNavigate();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [sidebarMonth, setSidebarMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selectedDay, setSelectedDay] = useState(() => {
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    return t;
  });
  const [view, setView] = useState("week");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ title: "", date: "", time: "09:00", duration: 30, type: "Internal", all_day: false });
  const [busy, setBusy] = useState(false);

  const weekParam = toIsoDate(weekStart);
  const { data, loading, error, reload } = useFetch(`/calendar?week_start=${weekParam}`, [weekParam]);

  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);
  const events = data?.events || data?.meetings || [];

  const goToday = () => {
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    const ws = startOfWeek(t);
    setWeekStart(ws);
    setSelectedDay(t);
    setSidebarMonth(new Date(t.getFullYear(), t.getMonth(), 1));
  };

  const shiftWeek = (delta) => {
    setWeekStart((ws) => addDays(ws, delta * 7));
  };

  const pickDay = (day) => {
    setSelectedDay(day);
    setWeekStart(startOfWeek(day));
    setSidebarMonth(new Date(day.getFullYear(), day.getMonth(), 1));
  };

  const openAdd = (day) => {
    setEditing(null);
    setForm({ title: "", date: toIsoDate(day || selectedDay), time: "09:00", duration: 30, type: "Internal", all_day: false });
    setShowForm(true);
  };

  const openEdit = (ev) => {
    if (ev.source !== "helm") return;
    setEditing(ev.id);
    setForm({
      title: ev.title,
      date: ev.date || toIsoDate(selectedDay),
      time: ev.time || "09:00",
      duration: ev.duration || 30,
      type: ev.type || "Internal",
      all_day: !!ev.all_day,
    });
    setShowForm(true);
  };

  const submitEvent = async () => {
    if (!form.title.trim()) { toast.error("Title is required"); return; }
    setBusy(true);
    try {
      if (editing) await api.patch(`/calendar/events/${editing}`, form);
      else await api.post("/calendar/events", form);
      toast.success(editing ? "Event updated" : "Event added");
      setShowForm(false);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save event"); }
    finally { setBusy(false); }
  };

  const deleteEvent = async () => {
    if (!editing || !window.confirm("Delete this event?")) return;
    setBusy(true);
    try {
      await api.delete(`/calendar/events/${editing}`);
      toast.success("Event deleted");
      setShowForm(false);
      reload();
    } catch (e) { toast.error("Could not delete"); }
    finally { setBusy(false); }
  };

  if (loading) return <LoadingScreen label="Loading calendar" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load calendar"
        message={fetchErrorMessage(error, "Calendar data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }

  const hasEvents = events.length > 0 || (data.upcoming || []).length > 0;
  const canWrite = data.can_write !== false;

  if (!hasEvents && !data.live && !canWrite) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-light tracking-tight text-white">Calendar</h1>
          <p className="text-zinc-500 text-sm mt-2">Week view with your meetings and Helm deadlines.</p>
        </div>
        <EmptyState
          icon={CalendarPlus}
          title="Connect Google Calendar"
          body="Bring your real schedule into Helm — deadlines from decisions and tasks appear automatically."
          action={(
            <button data-testid="connect-calendar-btn" onClick={() => navigate("/app/integrations")}
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover">
              <CalendarPlus className="w-4 h-4" /> Connect Google Calendar
            </button>
          )}
        />
      </div>
    );
  }

  return (
    <div className="fade-up -mx-2 md:-mx-4">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-4 px-2 md:px-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-light tracking-tight text-white">Calendar</h1>
          <p className="text-zinc-500 text-sm mt-1">
            {data.source === "google_calendar" ? "Live from Google Calendar" : "Your schedule and Helm deadlines"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {canWrite && (
            <button type="button" data-testid="add-event-btn" onClick={() => openAdd(selectedDay)}
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-3 py-2 hover:bg-gold-hover">
              <Plus className="w-4 h-4" /> Add event
            </button>
          )}
          <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.02] p-1">
            <button type="button" onClick={() => shiftWeek(-1)} className="p-1.5 text-zinc-400 hover:text-white rounded" aria-label="Previous week">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button type="button" onClick={goToday} className="px-3 py-1 text-zinc-300 hover:text-white font-mono text-xs uppercase tracking-wider">
              Today
            </button>
            <button type="button" onClick={() => shiftWeek(1)} className="p-1.5 text-zinc-400 hover:text-white rounded" aria-label="Next week">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          <div className="flex rounded-lg border border-white/10 overflow-hidden">
            {["day", "week", "month"].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className={cn(
                  "px-3 py-1.5 text-xs font-mono uppercase tracking-wider capitalize",
                  view === v ? "bg-gold/15 text-gold" : "text-zinc-500 hover:text-zinc-300",
                )}
              >
                {v}
              </button>
            ))}
          </div>
          <div className="hidden sm:flex items-center gap-4 text-xs text-zinc-500 font-mono">
            <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-gold" />{data.focus_hours ?? 0}h focus</span>
            <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5 text-gold" />{data.meeting_hours ?? 0}h meetings</span>
          </div>
        </div>
      </div>

      <div
        className="flex rounded-xl border border-white/[0.08] bg-[#09090b] overflow-hidden min-h-[560px] lg:min-h-[calc(100vh-12rem)]"
        data-testid="calendar-week-layout"
      >
        <aside className="hidden md:flex w-[260px] lg:w-[280px] shrink-0 flex-col border-r border-white/10 bg-[#070708]">
          <MiniMonth
            month={sidebarMonth}
            selected={selectedDay}
            weekDays={weekDays}
            onSelectDay={pickDay}
            onPrev={() => setSidebarMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
            onNext={() => setSidebarMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
          />
          <AgendaSidebar events={events} weekDays={weekDays} selectedDay={selectedDay} onSelectDay={pickDay} />
        </aside>

        <div className="flex-1 flex flex-col min-w-0 bg-[#0c0c0e]">
          {view === "week" && (
            <WeekGrid weekDays={weekDays} events={events} selectedDay={selectedDay} onEventClick={openEdit} />
          )}
          {view === "day" && (
            <WeekGrid weekDays={[selectedDay]} events={events.filter((ev) => {
              const s = parseEventStart(ev);
              return s && sameDay(s, selectedDay);
            })} selectedDay={selectedDay} onEventClick={openEdit} />
          )}
          {view === "month" && (
            <div className="p-4 flex-1 overflow-auto">
              <MiniMonth
                month={sidebarMonth}
                selected={selectedDay}
                weekDays={weekDays}
                onSelectDay={(d) => { pickDay(d); setView("day"); }}
                onPrev={() => setSidebarMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
                onNext={() => setSidebarMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
              />
              <p className="text-sm text-zinc-500 mt-4 px-4">Select a day to open the detailed schedule.</p>
            </div>
          )}
        </div>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          <div className="absolute inset-0 bg-black/70" onClick={() => setShowForm(false)} />
          <GlassCard className="relative w-full sm:max-w-md m-0 sm:m-4 rounded-t-2xl sm:rounded-2xl p-6" data-testid="event-form">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg text-white font-light">{editing ? "Edit event" : "Add event"}</h3>
              <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <label className="text-xs text-zinc-500 block">Title
                <input data-testid="event-title" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-zinc-500">Date
                  <input type="date" data-testid="event-date" value={form.date} onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
                </label>
                <label className="text-xs text-zinc-500">Type
                  <select value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40">
                    {["Internal", "Sales", "1:1", "Board"].map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </label>
              </div>
              <label className="flex items-center gap-2 text-sm text-zinc-300">
                <input type="checkbox" checked={form.all_day} onChange={(e) => setForm((f) => ({ ...f, all_day: e.target.checked }))} className="accent-gold" />
                All day
              </label>
              {!form.all_day && (
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-xs text-zinc-500">Start time
                    <input type="time" value={form.time} onChange={(e) => setForm((f) => ({ ...f, time: e.target.value }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
                  </label>
                  <label className="text-xs text-zinc-500">Duration (min)
                    <input type="number" min={15} step={15} value={form.duration} onChange={(e) => setForm((f) => ({ ...f, duration: parseInt(e.target.value, 10) || 30 }))} className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40" />
                  </label>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-5">
              {editing && (
                <button type="button" onClick={deleteEvent} disabled={busy} className="rounded-md border border-rose-500/40 text-rose-300 text-sm px-4 py-2.5 hover:bg-rose-500/10 disabled:opacity-60">Delete</button>
              )}
              <button data-testid="submit-event-btn" onClick={submitEvent} disabled={busy} className="flex-1 rounded-md bg-gold text-black font-medium py-2.5 text-sm hover:bg-gold-hover disabled:opacity-60">{busy ? "Saving…" : editing ? "Save event" : "Add event"}</button>
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
