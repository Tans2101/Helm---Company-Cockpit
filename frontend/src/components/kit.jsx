import { cn } from "@/lib/utils";

export function GlassCard({ className, children, glow, ...props }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-helm-line bg-helm-card",
        glow && "border-helm-gold/35",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between mb-8 fade-up">
      <div>
        <h1 className="font-display text-3xl md:text-4xl font-normal tracking-tight text-helm-fg">{title}</h1>
        {subtitle && <p className="text-helm-muted text-sm mt-2 max-w-2xl font-sans">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function SectionLabel({ children, className }) {
  return (
    <h2 className={cn("font-display text-sm font-medium tracking-tight text-helm-fg", className)}>
      {children}
    </h2>
  );
}

const toneColor = {
  positive: "text-helm-status-positive",
  negative: "text-helm-status-negative",
  neutral: "text-helm-muted",
};

export function Delta({ value, tone, invert }) {
  if (value === 0 || value === undefined || value === null) {
    return <span className="text-helm-muted font-mono text-xs">—</span>;
  }
  const up = value > 0;
  const effectiveTone = tone || (up ? "positive" : "negative");
  return (
    <span className={cn("font-mono text-xs", toneColor[effectiveTone])}>
      {up ? "▲" : "▼"} {Math.abs(value)}%
    </span>
  );
}

export function ProBadge({ className }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border border-helm-gold/40 bg-helm-gold/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-helm-gold", className)}>
      Active
    </span>
  );
}

export function Spinner({ className }) {
  return <div className={cn("w-5 h-5 rounded-full border-2 border-helm-gold/30 border-t-helm-gold animate-spin", className)} />;
}

export function LoadingScreen({ label = "Loading" }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-32">
      <Spinner className="w-6 h-6 mb-4" />
      <p className="font-mono text-xs uppercase tracking-[0.25em] text-helm-muted">{label}</p>
    </div>
  );
}

export function ErrorScreen({ label = "Something went wrong", message, onRetry }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-32 px-6 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.25em] text-helm-status-negative/80 mb-3">{label}</p>
      <p className="text-sm text-helm-muted max-w-md leading-relaxed">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 rounded-md border border-helm-line bg-helm-fg/5 px-4 py-2 text-sm text-helm-fg transition-colors hover:border-helm-gold/30 hover:text-helm-fg"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, body, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-24 px-6 fade-up">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-helm-navy/5 border border-helm-line flex items-center justify-center mb-5">
          <Icon className="w-6 h-6 text-helm-gold" />
        </div>
      )}
      <h3 className="font-display text-xl text-helm-fg font-medium tracking-tight">{title}</h3>
      {body && <p className="text-sm text-helm-muted mt-2 max-w-sm leading-relaxed font-sans">{body}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/** In-app confirm — replaces native window.confirm so dialogs match Helm. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  destructive = true,
  busy = false,
  onConfirm,
  onCancel,
  testId = "confirm-dialog",
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid={testId} role="alertdialog" aria-modal="true">
      <div
        className="absolute inset-0 bg-helm-ink/70"
        onClick={() => !busy && onCancel?.()}
        aria-hidden="true"
      />
      <div className="relative w-full max-w-sm rounded-md border border-helm-line bg-helm-card p-5 space-y-3 shadow-xl">
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-helm-fg">{title}</p>
          {description ? (
            <p className="text-sm text-helm-muted leading-relaxed">{description}</p>
          ) : null}
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            disabled={busy}
            data-testid={`${testId}-cancel`}
            onClick={() => onCancel?.()}
            className="rounded-md border border-helm-line text-sm px-3 py-2 text-helm-fg hover:bg-helm-fg/[0.04] disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            disabled={busy}
            data-testid={`${testId}-confirm`}
            onClick={() => onConfirm?.()}
            className={cn(
              "rounded-md text-sm font-medium px-3 py-2 disabled:opacity-50",
              destructive
                ? "border border-helm-status-negative/40 bg-helm-status-negative/15 text-helm-status-negative hover:bg-helm-status-negative/25"
                : "bg-helm-gold text-helm-navy hover:bg-helm-gold-hover",
            )}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
