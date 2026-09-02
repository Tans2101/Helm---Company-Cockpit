import { Clock, Users, Sparkles, CalendarPlus, CalendarClock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const typeStyle = {
  Sales: "text-gold bg-gold/10",
  Internal: "text-sky-400 bg-sky-400/10",
  "1:1": "text-emerald-400 bg-emerald-400/10",
  Board: "text-violet-400 bg-violet-400/10",
};

function fmtDate(d) {
  try { return new Date(d + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  catch (e) { return d; }
}

export default function CalendarPage() {
  const { data, loading, error, reload } = useFetch("/calendar");
  const navigate = useNavigate();
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

  const meetings = data.meetings || [];
  const upcoming = data.upcoming || [];

  if (meetings.length === 0 && upcoming.length === 0) {
    return (
      <div>
        <PageHeader title="Calendar" subtitle="Your schedule and upcoming deadlines in one place." />
        <EmptyState
          icon={CalendarPlus}
          title={data.live ? "Nothing scheduled yet" : "Connect Google Calendar"}
          body={data.live ? "Meetings and decision deadlines will appear here as they're added." : "Bring your real schedule into Helm — and set due dates on decisions to see deadlines here."}
          action={!data.live ? (
            <button data-testid="connect-calendar-btn" onClick={() => navigate("/app/integrations")}
              className="inline-flex items-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2 hover:bg-gold-hover">
              <CalendarPlus className="w-4 h-4" /> Connect Google Calendar
            </button>
          ) : null}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Calendar"
        subtitle={data.source === "google_calendar" ? "Live from Google Calendar — today's meetings and your deadlines." : "Your schedule and upcoming deadlines in one place."}
      />

      {upcoming.length > 0 && (
        <div className="mb-8">
          <SectionLabel className="mb-3">Upcoming deadlines</SectionLabel>
          <div className="space-y-2">
            {upcoming.map((u) => (
              <GlassCard key={u.id} className="p-3.5 fade-up flex items-center gap-4" data-testid={`upcoming-${u.id}`}>
                <div className="w-16 shrink-0 text-center rounded-md border border-gold/20 bg-gold/[0.06] py-1.5">
                  <p className="font-mono text-gold text-sm">{fmtDate(u.date)}</p>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{u.title}</p>
                  <p className="text-[11px] text-zinc-500">{u.type}{u.meta ? ` · ${u.meta}` : ""}</p>
                </div>
                <CalendarClock className="w-4 h-4 text-zinc-600 shrink-0" />
              </GlassCard>
            ))}
          </div>
        </div>
      )}

      {meetings.length > 0 && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <GlassCard className="p-5 fade-up">
              <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-gold" /><p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Focus time</p></div>
              <p className="font-mono text-3xl text-white mt-2">{data.focus_hours}h</p>
            </GlassCard>
            <GlassCard className="p-5 fade-up">
              <div className="flex items-center gap-2"><Users className="w-4 h-4 text-gold" /><p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">In meetings</p></div>
              <p className="font-mono text-3xl text-white mt-2">{data.meeting_hours}h</p>
            </GlassCard>
            <GlassCard className="p-5 fade-up">
              <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-zinc-500">Meetings today</p>
              <p className="font-mono text-3xl text-white mt-2">{meetings.length}</p>
            </GlassCard>
          </div>

          <SectionLabel className="mb-4">Today's schedule</SectionLabel>
          <div className="space-y-3">
            {meetings.map((m) => (
              <GlassCard key={m.id} className="p-4 fade-up" data-testid={`meeting-${m.id}`}>
                <div className="flex items-center gap-4">
                  <div className="w-16 shrink-0 text-center">
                    <p className="font-mono text-lg text-white">{m.time}</p>
                    <p className="text-[10px] text-zinc-600">{m.duration}m</p>
                  </div>
                  <div className="w-px self-stretch bg-white/5" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-white font-medium">{m.title}</h3>
                      <span className={cn("text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5", typeStyle[m.type])}>{m.type}</span>
                      <span className="text-[11px] text-zinc-600 flex items-center gap-1"><Users className="w-3 h-3" />{m.attendees}</span>
                    </div>
                    {m.prep && (
                      <div className="flex items-start gap-1.5 mt-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-gold mt-0.5 shrink-0" />
                        <p className="text-sm text-zinc-400 leading-relaxed">{m.prep}</p>
                      </div>
                    )}
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
