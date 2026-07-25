import { cn } from "@/lib/utils";

export function GlassCard({ className, children, glow, ...props }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-white/[0.06] bg-[#121214]/80 backdrop-blur-xl",
        glow && "shadow-[0_0_40px_-12px_rgba(201,169,98,0.25)]",
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
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">{title}</h1>
        {subtitle && <p className="text-zinc-500 text-sm mt-2 max-w-2xl">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function SectionLabel({ children, className }) {
  return (
    <h4 className={cn("text-[11px] font-mono font-medium uppercase tracking-[0.2em] text-gold", className)}>
      {children}
    </h4>
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
      Pro
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
