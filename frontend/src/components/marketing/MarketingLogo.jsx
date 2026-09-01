import { Link } from "react-router-dom";
import { CATEGORY } from "@/lib/marketingCopy";

/** Clickable Helm mark — always routes to the marketing home page. */
export default function MarketingLogo({ size = "md", showTagline = false, className = "" }) {
  const box = size === "sm" ? "w-7 h-7" : "w-9 h-9";
  const letter = size === "sm" ? "text-sm" : "text-base";
  const name = size === "sm" ? "text-sm" : "text-base";

  return (
    <Link
      to="/"
      className={`inline-flex items-center gap-2.5 group transition-opacity hover:opacity-90 ${className}`}
      aria-label="Helm home"
      data-testid="helm-logo-home"
    >
      <div className={`${box} rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center shrink-0`}>
        <span className={`font-mono text-gold font-medium ${letter}`}>H</span>
      </div>
      <div>
        <p className={`text-white font-semibold tracking-tight leading-none ${name}`}>Helm</p>
        {showTagline && (
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mt-1">{CATEGORY}</p>
        )}
      </div>
    </Link>
  );
}
