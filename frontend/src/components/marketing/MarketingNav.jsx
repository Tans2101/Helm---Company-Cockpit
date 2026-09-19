import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Menu, X } from "lucide-react";
import MarketingLogo from "@/components/marketing/MarketingLogo";
import SmoothTab, { SmoothTabItem } from "@/components/kokonutui/smooth-tab";
import { cn } from "@/lib/utils";
import { PUBLIC_CONTACT_MAILTO } from "@/lib/marketingCopy";

const NAV_LINKS = [
  { to: "/", label: "Home", match: ["/"] },
  { to: "/features", label: "Features", match: ["/features"] },
  { to: "/integrations", label: "Integrations", match: ["/integrations"] },
  { to: "/about", label: "About", match: ["/about"] },
  { to: "/security", label: "Security", match: ["/security"] },
  { to: "/pricing", label: "Pricing", match: ["/pricing"] },
];

function isActive(path, active) {
  if (path === "/") return active === "/";
  return active === path || active?.startsWith(path);
}

export default function MarketingNav({ authed, onEnter, active }) {
  const [open, setOpen] = useState(false);

  const activeId = NAV_LINKS.find((l) => isActive(l.to, active))?.to || null;

  const renderLink = (l, className) => (
    <Link key={l.to} to={l.to} className={className} onClick={() => setOpen(false)}>
      {l.label}
    </Link>
  );

  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-helm-cream/10 bg-helm-ink/90 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex h-16 items-center justify-between">
          <MarketingLogo size="sm" dark />

          <nav className="hidden md:block" aria-label="Main">
            <SmoothTab
              orientation="horizontal"
              variant="underline"
              activeId={activeId}
              className="flex items-center gap-6"
            >
              {NAV_LINKS.map((l) => (
                <SmoothTabItem key={l.to} id={l.to} className="w-fit shrink-0 pb-0.5">
                  {renderLink(
                    l,
                    cn(
                      "text-sm transition-colors",
                      isActive(l.to, active)
                        ? "text-helm-cream font-medium"
                        : "text-helm-slate hover:text-helm-cream",
                    ),
                  )}
                </SmoothTabItem>
              ))}
            </SmoothTab>
          </nav>

          <div className="flex items-center gap-3">
            <a
              href={PUBLIC_CONTACT_MAILTO}
              data-testid="nav-contact-link"
              className="hidden sm:inline text-sm text-helm-slate hover:text-helm-cream transition-colors"
            >
              Contact
            </a>
            {!authed && (
              <Link to="/login" className="hidden sm:inline text-sm text-helm-slate hover:text-helm-cream transition-colors">
                Sign in
              </Link>
            )}
            <button
              data-testid="nav-signin-btn"
              type="button"
              onClick={onEnter}
              className="group hidden sm:flex items-center gap-1.5 rounded-md bg-helm-cream text-helm-navy text-sm font-medium px-4 py-2 transition-colors hover:bg-helm-gold"
            >
              {authed ? "Open cockpit" : "Get started"}
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
            </button>
            <button
              type="button"
              className="md:hidden text-helm-slate hover:text-helm-cream p-1"
              aria-label={open ? "Close menu" : "Open menu"}
              onClick={() => setOpen((o) => !o)}
            >
              {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {open && (
          <nav className="md:hidden mt-2 rounded-xl border border-helm-cream/10 bg-helm-ink-card p-4 space-y-1" aria-label="Mobile">
            {NAV_LINKS.map((l) =>
              renderLink(
                l,
                `block rounded-lg px-3 py-2.5 text-sm ${isActive(l.to, active) ? "bg-helm-cream/5 text-helm-cream" : "text-helm-slate hover:text-helm-cream"}`,
              ),
            )}
            <a
              href={PUBLIC_CONTACT_MAILTO}
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2.5 text-sm text-helm-slate hover:text-helm-cream"
            >
              Contact
            </a>
            <div className="pt-2 border-t border-helm-cream/10 flex flex-col gap-2">
              {!authed && (
                <Link to="/login" onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2.5 text-sm text-helm-slate hover:text-helm-cream">
                  Sign in
                </Link>
              )}
              <button
                type="button"
                onClick={() => { setOpen(false); onEnter?.(); }}
                className="w-full rounded-md bg-helm-cream text-helm-navy text-sm font-medium px-3 py-2.5 hover:bg-helm-gold transition-colors"
              >
                {authed ? "Open cockpit" : "Get started"}
              </button>
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
