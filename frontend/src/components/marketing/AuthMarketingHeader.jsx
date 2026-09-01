import { Link } from "react-router-dom";
import MarketingLogo from "@/components/marketing/MarketingLogo";

const LINKS = [
  { to: "/", label: "Home" },
  { to: "/features", label: "Features" },
  { to: "/about", label: "About" },
  { to: "/#pricing", label: "Pricing" },
];

/** Top bar for login / sign-up — logo goes home; explore links stay visible. */
export default function AuthMarketingHeader() {
  return (
    <header className="absolute top-0 inset-x-0 z-20 px-6 py-6 md:px-10 md:py-8">
      <div className="flex items-center justify-between gap-4 max-w-6xl mx-auto">
        <MarketingLogo size="md" showTagline />
        <nav className="flex flex-wrap items-center justify-end gap-x-5 gap-y-1 text-sm text-zinc-500">
          {LINKS.map((l) => (
            <Link key={l.to} to={l.to} className="hover:text-white transition-colors whitespace-nowrap">
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
