import { Link } from "react-router-dom";
import { CATEGORY } from "@/lib/marketingCopy";
import helmMark from "@/assets/helm-mark.svg";
import helmMarkNavy from "@/assets/helm-mark-navy.svg";

/** Clickable Helm mark — always routes to the marketing home page. */
export default function MarketingLogo({ size = "md", showTagline = false, className = "", dark = false }) {
  const box = size === "sm" ? "w-7 h-7" : "w-9 h-9";
  const name = size === "sm" ? "text-sm" : "text-base";

  return (
    <Link
      to="/"
      className={`inline-flex items-center gap-2.5 group transition-opacity hover:opacity-90 ${className}`}
      data-testid="helm-logo-home"
    >
      <img
        src={dark ? helmMarkNavy : helmMark}
        alt=""
        width={size === "sm" ? 28 : 36}
        height={size === "sm" ? 28 : 36}
        className={`${box} shrink-0 rounded-md`}
        draggable={false}
      />
      <div>
        <p className={`font-semibold tracking-tight leading-none ${name} ${dark ? "text-helm-cream" : "text-helm-navy"}`}>Helm</p>
        {showTagline && (
          <p className={`text-[10px] font-mono uppercase tracking-[0.2em] mt-1 ${dark ? "text-helm-slate" : "text-helm-slate"}`}>{CATEGORY}</p>
        )}
      </div>
    </Link>
  );
}
