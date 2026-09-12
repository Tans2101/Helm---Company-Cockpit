import { useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Send, UserCheck, Users, CheckCircle2, Circle, Mail } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { GlassCard, LoadingScreen, ErrorScreen, Delta } from "@/components/kit";
import { cn } from "@/lib/utils";
import Onboarding from "@/pages/Onboarding";
import { timeGreeting } from "@/lib/greeting";

const toneDot = { positive: "bg-emerald-500", negative: "bg-rose-500", neutral: "bg-zinc-400" };

function BriefLabel({ children, className }) {
  return (
    <h2 className={cn("text-sm font-medium tracking-tight text-zinc-300", className)}>
      {children}
    </h2>
  );
}

export default function Briefing() {
  const { data, loading: briefingLoading, error: briefingError, reload: reloadBriefing, setData } = useFetch("/briefing");
  const { data: company, loading: companyLoading, error: companyError, reload: reloadCompany } = useFetch("/company");
  const { data: checklist } = useFetch("/onboarding/checklist");
  const [genLoading, setGenLoading] = useState(false);
  const [delegateBusy, setDelegateBusy] = useState(null);
  const navigate = useNavigate();

  const loading = briefingLoading || companyLoading;
  const error = briefingError || companyError;
  const reload = () => { reloadBriefing(); reloadCompany(); };

  if (loading) return <LoadingScreen label="Loading briefing" />;
  if (error || !data || !company) {
    return (
      <ErrorScreen
        label="Could not load briefing"
        message={fetchErrorMessage(error, "Briefing data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  if (company.onboarding_done === false) return <Onboarding />;

  const generate = async () => {
    setGenLoading(true);
    try {
      const { data: res } = await api.post("/briefing/generate");
      setData({ ...data, ai_summary: res.ai_summary });
      toast.success("Briefing updated");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate briefing");
    } finally {
      setGenLoading(false);
    }
  };

  const assignDelegate = async (id) => {
    setDelegateBusy(id);
    try {
      await api.post(`/delegates/suggestions/${id}/assign`);
      toast.success("Task created");
      reloadBriefing();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not assign task");
    } finally {
      setDelegateBusy(null);
    }
  };

  const dismissDelegate = async (id) => {
    setDelegateBusy(id);
    try {
      await api.post(`/delegates/suggestions/${id}/dismiss`);
      toast.success("Suggestion dismissed");
      reloadBriefing();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not dismiss");
    } finally {
      setDelegateBusy(null);
    }
  };

  const { greeting: timeGreet, briefingLabel } = timeGreeting();
  const greeting = `${timeGreet}, ${company?.ceo_name?.split(" ")[0] || "CEO"}`;
  const doneCount = checklist?.steps?.filter((s) => s.done).length ?? 0;
  const stepCount = checklist?.steps?.length ?? 0;

  return (
    <div className="max-w-5xl">
      <header className="mb-8 fade-up">
        <p className="text-xs uppercase tracking-[0.18em] text-zinc-500 mb-3">
          {data.date} · {briefingLabel}
        </p>
        <h1 className="text-3xl md:text-4xl font-medium tracking-tight text-white">{greeting}.</h1>
        <p className="text-zinc-400 mt-3 max-w-2xl text-base leading-relaxed">{data.headline}</p>
      </header>

      {checklist && !checklist.complete && (
        <section className="mb-6 fade-up rounded-xl border border-white/[0.08] bg-helm-card/80 p-5" data-testid="onboarding-checklist">
          <div className="flex items-center gap-3 mb-4">
            <BriefLabel>Finish setting up</BriefLabel>
            <span className="ml-auto text-xs text-zinc-500 tabular-nums">{doneCount}/{stepCount}</span>
          </div>
          <div className="h-1 rounded-full bg-white/[0.06] mb-4 overflow-hidden">
            <div
              className="h-full rounded-full bg-gold/70 transition-all"
              style={{ width: stepCount ? `${(doneCount / stepCount) * 100}%` : "0%" }}
            />
          </div>
          <div className="grid sm:grid-cols-2 gap-2">
            {checklist.steps.map((s) => (
              <button
                key={s.id}
                data-testid={`setup-${s.id}`}
                onClick={() => navigate(s.route)}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors",
                  s.done
                    ? "border-emerald-500/20 bg-emerald-500/[0.04]"
                    : "border-white/10 bg-white/[0.02] hover:border-white/20"
                )}
              >
                {s.done
                  ? <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  : <Circle className="w-4 h-4 text-zinc-500 shrink-0" />}
                <span className={cn("text-sm", s.done ? "text-zinc-500 line-through" : "text-zinc-200")}>
                  {s.label}
                </span>
                {!s.done && <ArrowUpRight className="w-3.5 h-3.5 text-zinc-500 ml-auto shrink-0" />}
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6">
        {data.metrics.map((m, i) => (
          <div
            key={m.label}
            className="rounded-xl border border-white/[0.08] bg-helm-card/80 p-4 fade-up"
            style={{ animationDelay: `${i * 60}ms` }}
            data-testid={`briefing-metric-${i}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider text-zinc-500">{m.label}</span>
              <span className={cn("w-1.5 h-1.5 rounded-full", toneDot[m.tone])} />
            </div>
            <div className="mt-3 flex items-end justify-between gap-2">
              <span className={cn("text-2xl md:text-3xl tabular-nums tracking-tight", m.missing ? "text-zinc-500" : "text-white")}>
                {m.value}
              </span>
              <Delta value={m.delta} tone={m.tone} />
            </div>
          </div>
        ))}
      </div>

      <section className="mb-6 fade-up rounded-xl border border-white/[0.08] bg-helm-card/80 p-5 md:p-6">
        <div className="flex items-center justify-between gap-3 mb-3">
          <BriefLabel>Today&apos;s summary</BriefLabel>
          {data.ai_summary && (
            <button
              type="button"
              data-testid="generate-briefing-btn"
              onClick={generate}
              disabled={genLoading}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50"
            >
              {genLoading ? "Updating…" : "Refresh"}
            </button>
          )}
        </div>
        {data.ai_summary ? (
          <p className="text-zinc-200 leading-relaxed text-[15px] max-w-3xl">{data.ai_summary}</p>
        ) : (
          <div>
            <p className="text-zinc-500 text-sm mb-4 max-w-xl">
              Pull a short plain-language read of what changed, what needs a decision, and what to watch — from your live company data.
            </p>
            <button
              data-testid="generate-briefing-btn"
              onClick={generate}
              disabled={genLoading}
              className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2 transition-colors hover:bg-gold-hover disabled:opacity-60"
            >
              {genLoading ? "Writing summary…" : "Write today\u2019s summary"}
              {!genLoading && <Send className="w-3.5 h-3.5" />}
            </button>
          </div>
        )}
      </section>

      {(data.email_threads?.length > 0 || data.gmail_connected || data.gmail_needs_reconnect) && (
        <GlassCard className="p-5 mb-6 fade-up" data-testid="briefing-email">
          <div className="flex items-center gap-2 mb-4">
            <Mail className="w-4 h-4 text-zinc-500" />
            <BriefLabel>Email</BriefLabel>
            {data.email_threads?.length > 0 && (
              <span className="text-xs tabular-nums text-zinc-500 ml-auto">{data.email_threads.length}</span>
            )}
          </div>
          {data.gmail_needs_reconnect && (
            <div className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3">
              <p className="text-sm text-zinc-300 leading-relaxed">
                Google is connected for Calendar. Reconnect once to enable Gmail in your briefing.
              </p>
              <button
                type="button"
                data-testid="enable-gmail-btn"
                onClick={() => navigate("/app/integrations")}
                className="mt-2 text-xs text-gold hover:text-gold-hover"
              >
                Enable Gmail →
              </button>
            </div>
          )}
          {data.email_threads?.length > 0 ? (
            <div className="space-y-3">
              {data.email_threads.map((t, i) => (
                <a
                  key={t.id || i}
                  href={t.thread_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid={`email-thread-${i}`}
                  className="block rounded-lg border border-white/5 bg-white/[0.02] p-3 transition-colors hover:border-white/15 hover:bg-white/[0.04] group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm text-white leading-snug truncate">{t.subject}</p>
                      <p className="text-xs text-zinc-500 mt-1 truncate">
                        {t.sender}{t.sender_email ? ` · ${t.sender_email}` : ""}
                      </p>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 shrink-0" />
                  </div>
                  {t.snippet && (
                    <p className="text-xs text-zinc-400 mt-2 leading-relaxed line-clamp-2">{t.snippet}</p>
                  )}
                </a>
              ))}
            </div>
          ) : data.gmail_connected ? (
            <p className="text-sm text-zinc-500 leading-relaxed">
              No important threads in the last two weeks. Starred or Gmail-important mail will show here.
            </p>
          ) : null}
        </GlassCard>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <GlassCard className="p-5 fade-up">
          <BriefLabel className="mb-4">What changed</BriefLabel>
          <div className="space-y-4">
            {data.what_changed.length === 0 && (
              <p className="text-sm text-zinc-500 leading-relaxed">Nothing new logged yet.</p>
            )}
            {data.what_changed.map((c, i) => (
              <div key={i} className="flex gap-3" data-testid={`changed-${i}`}>
                <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", toneDot[c.tone])} />
                <div>
                  <p className="text-sm text-white leading-snug">{c.title}</p>
                  <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{c.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="p-5 fade-up">
          <div className="flex items-center justify-between mb-4">
            <BriefLabel>What to decide</BriefLabel>
            <span className="text-xs tabular-nums text-zinc-500">{data.what_to_decide.length}</span>
          </div>
          <div className="space-y-3">
            {data.what_to_decide.length === 0 && (
              <p className="text-sm text-zinc-500 leading-relaxed">No open decisions. Log one when something needs a call.</p>
            )}
            {data.what_to_decide.map((d) => (
              <button
                key={d.id}
                onClick={() => navigate("/app/decisions")}
                data-testid={`decide-${d.id}`}
                className="w-full text-left rounded-lg border border-white/5 bg-white/[0.02] p-3 transition-colors hover:border-white/15 hover:bg-white/[0.04] group"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-white leading-snug">{d.title}</p>
                  <ArrowUpRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 shrink-0" />
                </div>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{d.detail}</p>
                <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                  <span
                    className={cn(
                      "inline-block text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded",
                      d.urgency === "high" ? "text-rose-400 bg-rose-400/10" : "text-amber-600 bg-amber-400/10"
                    )}
                  >
                    {d.urgency} priority
                  </span>
                  {d.source === "ai_suggested" && (
                    <span className="inline-block text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded text-zinc-400 bg-white/[0.04]">
                      Suggested{d.confidence != null ? ` · ${d.confidence}%` : ""}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="p-5 fade-up">
          <BriefLabel className="mb-4">What to hand off</BriefLabel>
          <div className="space-y-3">
            {data.what_to_delegate.length === 0 && (
              <p className="text-sm text-zinc-500 leading-relaxed">No handoffs suggested. Overdue work will show up here.</p>
            )}
            {data.what_to_delegate.map((d, i) => (
              <div key={d.id || i} className="rounded-lg border border-white/5 bg-white/[0.02] p-3" data-testid={`delegate-${d.id || i}`}>
                <p className="text-sm text-white leading-snug">{d.title}</p>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{d.detail}</p>
                <div className="flex items-center gap-1.5 mt-2 text-zinc-400">
                  <UserCheck className="w-3.5 h-3.5" />
                  <span className="text-xs">{d.owner || d.suggested_owner_name}</span>
                </div>
                {d.source === "ai_suggested" && d.id && (
                  <div className="flex gap-2 mt-3">
                    <button
                      data-testid={`assign-delegate-${d.id}`}
                      disabled={delegateBusy === d.id}
                      onClick={() => assignDelegate(d.id)}
                      className="flex-1 rounded-md bg-gold text-black text-xs font-medium py-1.5 hover:bg-gold-hover disabled:opacity-50"
                    >
                      Assign as task
                    </button>
                    <button
                      data-testid={`dismiss-delegate-${d.id}`}
                      disabled={delegateBusy === d.id}
                      onClick={() => dismissDelegate(d.id)}
                      className="rounded-md border border-white/10 text-zinc-400 text-xs px-2 py-1.5 hover:bg-white/5 disabled:opacity-50"
                    >
                      Dismiss
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {data.team_updates && data.team_updates.length > 0 && (
        <GlassCard className="p-5 mt-4 fade-up" data-testid="briefing-team-updates">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-4 h-4 text-zinc-500" />
            <BriefLabel>Today&apos;s team updates</BriefLabel>
            <span className="text-xs tabular-nums text-zinc-500 ml-auto">{data.team_updates.length}</span>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {data.team_updates.map((u, i) => (
              <div key={i} className="rounded-lg border border-white/5 bg-white/[0.02] p-3" data-testid={`team-update-${i}`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-white">{u.user_name}</span>
                  {u.blocker && (
                    <span className="text-[10px] text-amber-600 bg-amber-400/10 rounded px-1.5 py-0.5 uppercase tracking-wide">
                      Blocked
                    </span>
                  )}
                  <span className="text-[10px] text-zinc-500 ml-auto">{u.ago}</span>
                </div>
                <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">{u.text}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  );
}
