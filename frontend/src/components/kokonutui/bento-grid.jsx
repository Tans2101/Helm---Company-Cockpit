/**
 * @author: @dorianbaffier / Helm
 * @description: Bento Grid — Helm metrics layout (KokonutUI, restyled)
 * @website: https://kokonutui.com
 */

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { Delta } from "@/components/kit";
import { cn } from "@/lib/utils";

const toneDot = {
  positive: "bg-helm-status-positive",
  negative: "bg-helm-status-negative",
  neutral: "bg-helm-muted",
};

/** Parse a display value like "$248K", "17 months", "12.5%" into animatable parts. */
function parseMetricValue(raw) {
  if (raw == null) return { prefix: "", number: null, suffix: "", fallback: "—" };
  const str = String(raw);
  const match = str.match(/^([^\d-]*)(-?\d+(?:\.\d+)?)(.*)$/);
  if (!match) return { prefix: "", number: null, suffix: "", fallback: str };
  return {
    prefix: match[1],
    number: Number(match[2]),
    suffix: match[3],
    fallback: str,
  };
}

function AnimatedMetricValue({ value, missing, className }) {
  const reduceMotion = useReducedMotion();
  const parsed = useMemo(() => parseMetricValue(value), [value]);
  const [display, setDisplay] = useState(() =>
    reduceMotion || parsed.number == null ? parsed.fallback : `${parsed.prefix}0${parsed.suffix}`
  );

  useEffect(() => {
    if (reduceMotion || parsed.number == null) {
      setDisplay(parsed.fallback);
      return undefined;
    }

    const start = 0;
    const end = parsed.number;
    const duration = 900;
    const frameRate = 1000 / 60;
    const totalFrames = Math.max(1, Math.round(duration / frameRate));
    let frame = 0;
    const decimals = String(end).includes(".") ? Math.min(2, (String(end).split(".")[1] || "").length) : 0;

    const id = setInterval(() => {
      frame += 1;
      const progress = Math.min(1, frame / totalFrames);
      const eased = 1 - (1 - progress) ** 3;
      const current = start + (end - start) * eased;
      const formatted = decimals > 0 ? current.toFixed(decimals) : String(Math.round(current));
      setDisplay(`${parsed.prefix}${formatted}${parsed.suffix}`);
      if (frame >= totalFrames) clearInterval(id);
    }, frameRate);

    return () => clearInterval(id);
  }, [parsed, reduceMotion, value]);

  return (
    <span className={cn("tabular-nums tracking-tight", missing ? "text-helm-muted" : "text-helm-fg", className)}>
      {display}
    </span>
  );
}

function cellClass(index, total) {
  // Varied bento proportions: first cell larger when there are 3+ metrics.
  if (total === 1) return "col-span-1";
  if (total === 2) return "col-span-1";
  if (total === 3) {
    if (index === 0) return "col-span-2 lg:col-span-1 lg:row-span-2";
    return "col-span-1";
  }
  // 4+
  if (index === 0) return "col-span-2 lg:col-span-2";
  return "col-span-1";
}

function gridClass(total) {
  if (total === 1) return "grid-cols-1 max-w-xs";
  if (total === 2) return "grid-cols-2 max-w-xl";
  if (total === 3) return "grid-cols-2 lg:grid-cols-3 lg:grid-rows-2";
  return "grid-cols-2 lg:grid-cols-4";
}

/**
 * Helm briefing metrics bento — driven entirely by `metrics` from the briefing API.
 */
export default function BentoGrid({ metrics = [], className }) {
  const reduceMotion = useReducedMotion();
  const list = Array.isArray(metrics) ? metrics : [];
  if (list.length === 0) return null;

  return (
    <motion.div
      className={cn("grid gap-3 md:gap-4 mb-6", gridClass(list.length), className)}
      initial={reduceMotion ? false : "hidden"}
      animate="visible"
      variants={{
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: { staggerChildren: reduceMotion ? 0 : 0.08 },
        },
      }}
    >
      {list.map((m, i) => (
        <motion.div
          key={m.label || i}
          data-testid={`briefing-metric-${i}`}
          className={cn(
            "rounded-xl border border-helm-line bg-helm-card p-4",
            cellClass(i, list.length),
            i === 0 && list.length >= 3 && "md:p-5",
          )}
          variants={{
            hidden: { opacity: 0, y: reduceMotion ? 0 : 12 },
            visible: {
              opacity: 1,
              y: 0,
              transition: { duration: reduceMotion ? 0 : 0.4, ease: [0.16, 1, 0.3, 1] },
            },
          }}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-helm-muted font-mono">{m.label}</span>
            <span className={cn("w-1.5 h-1.5 rounded-full", toneDot[m.tone] || toneDot.neutral)} />
          </div>
          <div className={cn("mt-3 flex items-end justify-between gap-2", i === 0 && list.length >= 3 && "mt-4")}>
            <AnimatedMetricValue
              value={m.value}
              missing={m.missing}
              className={cn(
                i === 0 && list.length >= 3 ? "text-3xl md:text-4xl" : "text-2xl md:text-3xl",
              )}
            />
            <Delta value={m.delta} tone={m.tone} />
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
