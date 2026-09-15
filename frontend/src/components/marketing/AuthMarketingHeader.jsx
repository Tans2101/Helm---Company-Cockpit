import { Link, useLocation, useNavigate } from "react-router-dom";
import MarketingLogo from "@/components/marketing/MarketingLogo";
import { goToHomeHash } from "@/lib/marketingHash";

const LINKS = [
  { to: "/", label: "Home" },
  { to: "/features", label: "Features" },
  { to: "/about", label: "About" },
  { to: "/security", label: "Security" },
  { to: "/#pricing", label: "Pricing", hash: "pricing" },
];

/** Top bar for login / sign-up. Logo goes home; explore links stay visible. */
export default function AuthMarketingHeader() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <header className="absolute top-0 inset-x-0 z-20 px-6 py-6 md:px-10 md:py-8">
      <div className="flex items-center justify-between gap-4 max-w-6xl mx-auto">
        <MarketingLogo size="md" showTagline dark />
        <nav className="flex flex-wrap items-center justify-end gap-x-5 gap-y-1 text-sm text-helm-slate">
          {LINKS.map((l) =>
            l.hash ? (
              <a
                key={l.to}
                href={l.to}
                className="hover:text-helm-cream transition-colors whitespace-nowrap"
                onClick={(e) => {
                  e.preventDefault();
                  goToHomeHash(navigate, location, l.hash);
                }}
              >
                {l.label}
              </a>
            ) : (
              <Link key={l.to} to={l.to} className="hover:text-helm-cream transition-colors whitespace-nowrap">
                {l.label}
              </Link>
            ),
          )}
        </nav>
      </div>
    </header>
  );
}
