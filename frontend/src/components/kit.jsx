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
  positive: "text-emerald-400",
  negative: "text-rose-400",
  neutral: "text-zinc-400",
};

export function Delta({ value, tone, invert }) {
  if (value === 0 || value === undefined || value === null) {
    return <span className="text-zinc-500 font-mono text-xs">—</span>;
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
    <span className={cn("inline-flex items-center gap-1 rounded-full border border-gold/40 bg-gold/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-gold", className)}>
      Active
    </span>
  );
}

export function Spinner({ className }) {
  return <div className={cn("w-5 h-5 rounded-full border-2 border-gold/30 border-t-gold animate-spin", className)} />;
}

export function LoadingScreen({ label = "Loading" }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-32">
      <Spinner className="w-6 h-6 mb-4" />
      <p className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-600">{label}</p>
    </div>
  );
}

export function ErrorScreen({ label = "Something went wrong", message, onRetry }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-32 px-6 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.25em] text-rose-400/80 mb-3">{label}</p>
      <p className="text-sm text-zinc-400 max-w-md leading-relaxed">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-200 transition-colors hover:border-gold/30 hover:text-white"
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
