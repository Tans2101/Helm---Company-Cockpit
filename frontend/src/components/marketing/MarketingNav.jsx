import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export default function MarketingNav({ authed, onEnter, active }) {
  const linkClass = (path) =>
    `text-sm transition-colors ${active === path ? "text-white" : "text-zinc-500 hover:text-white"}`;

  return (
    <header className="fixed top-0 inset-x-0 z-50">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mt-4 flex items-center justify-between rounded-full border border-white/[0.06] bg-[#0d0d0f]/70 backdrop-blur-xl px-5 py-2.5">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
              <span className="font-mono text-gold text-sm font-medium">H</span>
            </div>
            <span className="text-white font-semibold tracking-tight">Helm</span>
          </Link>
          <nav className="hidden sm:flex items-center gap-6">
            <Link to="/features" className={linkClass("/features")}>Features</Link>
            <Link to="/about" className={linkClass("/about")}>About</Link>
            <Link to="/#pricing" className={linkClass("/#pricing")}>Pricing</Link>
          </nav>
          <button
            data-testid="nav-signin-btn"
            type="button"
            onClick={onEnter}
            className="group flex items-center gap-1.5 rounded-full bg-white text-black text-sm font-medium px-4 py-1.5 transition-colors hover:bg-gold"
          >
            {authed ? "Open cockpit" : "Sign in"}
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      </div>
    </header>
  );
}
