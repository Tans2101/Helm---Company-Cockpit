import { Link } from "react-router-dom";
import { Instagram } from "lucide-react";
import MarketingLogo from "@/components/marketing/MarketingLogo";
import FounderCredit from "@/components/marketing/FounderCredit";
import {
  CATEGORY,
  PUBLIC_CONTACT_EMAIL,
  PUBLIC_CONTACT_MAILTO,
  PUBLIC_INSTAGRAM_HANDLE,
  PUBLIC_INSTAGRAM_URL,
  TAGLINE,
} from "@/lib/marketingCopy";

const FOOTER_LINKS = [
  { to: "/", label: "Home" },
  { to: "/features", label: "Features" },
  { to: "/integrations", label: "Integrations" },
  { to: "/pricing", label: "Pricing" },
  { to: "/about", label: "About" },
  { to: "/help", label: "Help" },
  { to: "/security", label: "Security" },
  { to: "/changelog", label: "Changelog" },
  { to: "/status", label: "Status" },
  { to: "/login", label: "Sign in" },
  { to: "/sign-up", label: "Create account" },
  { to: "/privacy", label: "Privacy" },
  { to: "/terms", label: "Terms" },
  { to: "/refunds", label: "Refunds" },
];

export default function MarketingFooter() {
  return (
    <footer className="px-6 py-12 border-t border-helm-cream/10 bg-helm-ink">
      <div className="mx-auto max-w-6xl flex flex-col gap-8">
        <p className="text-center text-sm text-helm-slate max-w-md mx-auto leading-relaxed">{TAGLINE}</p>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-8">
          <div className="flex flex-col gap-2">
            <MarketingLogo size="sm" showTagline dark />
            <p className="text-xs text-helm-slate max-w-xs leading-relaxed mt-1">
              The {CATEGORY.toLowerCase()} for CEOs running companies of up to 50 people. One cockpit. Clear decisions. Quiet control.
            </p>
            <a href={PUBLIC_CONTACT_MAILTO} className="text-xs text-helm-slate hover:text-helm-cream transition-colors mt-2">
              {PUBLIC_CONTACT_EMAIL}
            </a>
            <a
              href={PUBLIC_INSTAGRAM_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Instagram ${PUBLIC_INSTAGRAM_HANDLE}`}
              title={`Instagram ${PUBLIC_INSTAGRAM_HANDLE}`}
              className="mt-1 inline-flex w-fit text-helm-slate hover:text-helm-cream transition-colors"
            >
              <Instagram className="h-4 w-4" aria-hidden />
            </a>
          </div>
          <nav className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-3 text-sm text-helm-slate" aria-label="Footer">
            {FOOTER_LINKS.map((l) => (
              <Link key={l.to + l.label} to={l.to} className="hover:text-helm-cream transition-colors">
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
        <p className="text-center text-[11px] text-helm-slate inline-flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1">
          <span>© {new Date().getFullYear()} Helm ·</span>
          <FounderCredit creditClassName="text-[11px] text-helm-slate" />
        </p>
      </div>
    </footer>
  );
}
