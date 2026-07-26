import { Clock, Users, Sparkles } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const typeStyle = {
  Sales: "text-gold bg-gold/10",
  Internal: "text-sky-400 bg-sky-400/10",
  "1:1": "text-emerald-400 bg-emerald-400/10",
  Board: "text-violet-400 bg-violet-400/10",
};

export default function CalendarPage() {
  const { data, loading } = useFetch("/calendar");
  if (loading || !data) return <LoadingScreen label="Loading calendar" />;
  if (data.meetings.length === 0) return <div><PageHeader title="Calendar" subtitle="Meeting intelligence — walk into every meeting prepared." /><EmptyState title="No meetings yet" body="Connect Google Calendar to bring your schedule and meeting prep into Helm." /></div>;

  return (
    <div>
      <PageHeader title="Calendar" subtitle="Meeting intelligence — what each meeting is for, who's in the room, and how to walk in prepared." />

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
          <p className="font-mono text-3xl text-white mt-2">{data.meetings.length}</p>
        </GlassCard>
      </div>

      <SectionLabel className="mb-4">Today's schedule</SectionLabel>
      <div className="space-y-3">
        {data.meetings.map((m) => (
          <GlassCard key={m.id} className="p-5 fade-up" data-testid={`meeting-${m.id}`}>
            <div className="flex flex-col md:flex-row md:items-center gap-4">
              <div className="w-20 shrink-0">
                <p className="font-mono text-xl text-white">{m.time}</p>
                <p className="text-xs text-zinc-600">{m.duration} min</p>
              </div>
              <div className="hidden md:block w-px self-stretch bg-white/5" />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-white font-medium">{m.title}</h3>
                  <span className={cn("text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5", typeStyle[m.type])}>{m.type}</span>
                  <span className="text-[11px] text-zinc-600 flex items-center gap-1"><Users className="w-3 h-3" />{m.attendees}</span>
                </div>
                <div className="flex items-start gap-1.5 mt-2">
                  <Sparkles className="w-3.5 h-3.5 text-gold mt-0.5 shrink-0" />
                  <p className="text-sm text-zinc-400 leading-relaxed">{m.prep}</p>
                </div>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
