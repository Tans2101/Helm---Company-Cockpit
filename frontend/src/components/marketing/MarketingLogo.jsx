import { Link } from "react-router-dom";
import { CATEGORY } from "@/lib/marketingCopy";

/** Clickable Helm mark — always routes to the marketing home page. */
export default function MarketingLogo({ size = "md", showTagline = false, className = "", dark = false }) {
  const box = size === "sm" ? "w-7 h-7" : "w-9 h-9";
  const letter = size === "sm" ? "text-sm" : "text-base";
  const name = size === "sm" ? "text-sm" : "text-base";

  return (
    <Link
      to="/"
      className={`inline-flex items-center gap-2.5 group transition-opacity hover:opacity-90 ${className}`}
      data-testid="helm-logo-home"
    >
      <div className={`${box} rounded-md ${dark ? "bg-gold/15 border-gold/30" : "bg-[#18211c] border-[#18211c]"} border flex items-center justify-center shrink-0`}>
        <span className={`font-mono ${dark ? "text-gold" : "text-[#f5d98b]"} font-medium ${letter}`}>H</span>
      </div>
      <div>
        <p className={`${dark ? "text-white" : "text-[#18211c]"} font-semibold tracking-tight leading-none ${name}`}>Helm</p>
        {showTagline && (
          <p className={`text-[10px] font-mono uppercase tracking-[0.2em] ${dark ? "text-zinc-400" : "text-[#68736b]"} mt-1`}>{CATEGORY}</p>
        )}
      </div>
    </Link>
  );
}
