import { Link } from "react-router-dom";
import MarketingLogo from "@/components/marketing/MarketingLogo";
import { CATEGORY, TAGLINE } from "@/lib/marketingCopy";

const FOOTER_LINKS = [
  { to: "/", label: "Home" },
  { to: "/features", label: "Features" },
  { to: "/about", label: "About" },
  { to: "/#pricing", label: "Pricing" },
  { to: "/login", label: "Sign in" },
  { to: "/sign-up", label: "Create account" },
  { to: "/privacy", label: "Privacy" },
  { to: "/terms", label: "Terms" },
  { to: "/refunds", label: "Refunds" },
];

export default function MarketingFooter() {
  return (
    <footer className="px-6 py-12 border-t border-white/[0.05]">
      <div className="mx-auto max-w-6xl flex flex-col gap-8">
        <p className="text-center text-sm text-zinc-600 italic max-w-md mx-auto leading-relaxed">{TAGLINE}</p>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-8">
          <div className="flex flex-col gap-2">
            <MarketingLogo size="sm" showTagline />
            <p className="text-xs text-zinc-600 max-w-xs leading-relaxed mt-1">
              The {CATEGORY.toLowerCase()} for seed & Series A CEOs. One cockpit. Clear decisions. Quiet control.
            </p>
          </div>
          <nav className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-3 text-sm text-zinc-500" aria-label="Footer">
            {FOOTER_LINKS.map((l) => (
              <Link key={l.to + l.label} to={l.to} className="hover:text-white transition-colors">
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <p className="text-center text-[11px] text-zinc-700">© {new Date().getFullYear()} Helm</p>
      </div>
    </footer>
  );
}
