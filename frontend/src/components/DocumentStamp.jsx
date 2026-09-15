import { cn } from "@/lib/utils";

/**
 * Circular navy outline stamp for document/export authenticity cues only
 * (Weekly CEO Pack, financial exports). Do not use for ordinary status badges.
 */
export default function DocumentStamp({ label = "Confirmed", className }) {
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      data-testid="document-stamp"
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
        "border border-helm-navy text-[8px] font-mono uppercase tracking-[0.12em] text-helm-navy",
        "rotate-[-12deg] select-none",
        className,
      )}
    >
      {label.length > 8 ? label.slice(0, 7) : label}
    </span>
  );
}

/** Status strings that earn a document stamp in export/pack previews. */
export function stampLabelForLine(text) {
  const t = String(text || "");
  if (/\bfiled\b/i.test(t)) return "Filed";
  if (/\bdelivered\b/i.test(t)) return "Delivered";
  if (/\bcompleted\b/i.test(t)) return "Completed";
  if (/\bsigned\b/i.test(t)) return "Signed";
  if (/\bconfirmed\b/i.test(t)) return "Confirmed";
  return null;
}
