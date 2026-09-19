import { Link } from "react-router-dom";
import MarketingLogo from "@/components/marketing/MarketingLogo";
import { PUBLIC_CONTACT_MAILTO } from "@/lib/marketingCopy";

const LINKS = [
  { to: "/", label: "Home" },
  { to: "/features", label: "Features" },
  { to: "/integrations", label: "Integrations" },
  { to: "/pricing", label: "Pricing" },
  { to: "/about", label: "About" },
  { to: "/security", label: "Security" },
];

/** Top bar for login / sign-up. Logo goes home; explore links stay visible. */
export default function AuthMarketingHeader() {
  return (
    <header className="absolute top-0 inset-x-0 z-20 px-6 py-6 md:px-10 md:py-8">
      <div className="flex items-center justify-between gap-4 max-w-6xl mx-auto">
        <MarketingLogo size="md" showTagline dark />
        <nav className="hidden sm:flex flex-wrap items-center justify-end gap-x-5 gap-y-1 text-sm text-helm-slate">
          {LINKS.map((l) => (
            <Link key={l.to} to={l.to} className="hover:text-helm-cream transition-colors whitespace-nowrap">
              {l.label}
            </Link>
          ))}
          <a href={PUBLIC_CONTACT_MAILTO} className="hover:text-helm-cream transition-colors whitespace-nowrap">
            Contact
          </a>
        </nav>
        <div className="sm:hidden flex items-center gap-4 text-sm text-helm-slate">
          <a href={PUBLIC_CONTACT_MAILTO} className="hover:text-helm-cream transition-colors">
            Contact
          </a>
          <Link to="/" className="hover:text-helm-cream transition-colors">
            ← Home
          </Link>
        </div>
      </div>
    </header>
  );
}
