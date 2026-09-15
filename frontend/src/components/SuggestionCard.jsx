import { Check, X, Sparkles } from "lucide-react";
import { GlassCard } from "@/components/kit";
import { ConfidenceBadge } from "@/components/DecisionCard";

export default function SuggestionCard({
  s,
  canAct,
  busy,
  onAcceptSuggestion,
  onDismissSuggestion,
}) {
  return (
    <GlassCard className="p-5 fade-up border-helm-status-warning/35" data-testid={`suggestion-${s.id}`}>
      <div className="flex flex-col lg:flex-row lg:items-start gap-5">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-helm-status-warning border border-helm-status-warning/35 rounded px-1.5 py-0.5">
              AI Suggested — verify before acting
            </span>
            <span className="text-[10px] font-mono uppercase tracking-wider text-helm-muted border border-helm-line rounded px-1.5 py-0.5">{s.category}</span>
            <span className="text-[10px] font-mono text-helm-muted">Impact: {s.impact}</span>
          </div>
          <h3 className="text-lg text-helm-fg font-medium tracking-tight">{s.title}</h3>
          {s.description && <p className="text-sm text-helm-muted mt-1">{s.description}</p>}
          {s.recommendation && (
            <div className="mt-4 rounded-lg border border-helm-line border-l-2 border-l-helm-status-warning/70 bg-helm-card p-3">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Sparkles className="w-3.5 h-3.5 text-helm-status-warning" />
                <span className="text-[11px] font-mono uppercase tracking-wider text-helm-status-warning">Helm recommendation</span>
                <ConfidenceBadge confidence={s.confidence} ai />
              </div>
              <p className="text-sm text-helm-fg leading-relaxed">{s.recommendation}</p>
              {s.confidence != null && (
                <div className="mt-2 h-1 rounded-full bg-helm-fg/5 overflow-hidden">
                  <div className="h-full bg-helm-status-warning/70 rounded-full" style={{ width: `${s.confidence}%` }} />
                </div>
              )}
            </div>
          )}
        </div>
        {canAct && (
          <div className="flex lg:flex-col gap-2 lg:w-40">
            <button
              data-testid={`approve-suggestion-${s.id}`}
              disabled={busy === s.id}
              onClick={() => onAcceptSuggestion(s.id)}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-helm-gold text-helm-navy text-sm font-medium py-2 hover:bg-helm-gold-hover disabled:opacity-50"
            >
              <Check className="w-4 h-4" /> Accept
            </button>
            <button
              data-testid={`dismiss-suggestion-${s.id}`}
              disabled={busy === s.id}
              onClick={() => onDismissSuggestion(s.id)}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-helm-line text-helm-muted text-sm py-2 hover:bg-helm-fg/5 hover:text-helm-status-negative disabled:opacity-50"
            >
              <X className="w-4 h-4" /> Dismiss
            </button>
          </div>
        )}
      </div>
    </GlassCard>
  );
}
