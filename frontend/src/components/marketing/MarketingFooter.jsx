import { Link } from "react-router-dom";
import { CATEGORY, TAGLINE } from "@/lib/marketingCopy";

export default function MarketingFooter() {
  return (
    <footer className="px-6 py-10 border-t border-white/[0.05]">
      <div className="mx-auto max-w-6xl flex flex-col gap-6">
        <p className="text-center text-sm text-zinc-600 italic">{TAGLINE}</p>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gold/15 border border-gold/30 flex items-center justify-center">
              <span className="font-mono text-gold text-xs">H</span>
            </div>
            <span className="text-sm text-zinc-500">Helm — {CATEGORY}</span>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-sm text-zinc-500">
            <Link to="/about" className="hover:text-white transition-colors">About</Link>
            <Link to="/features" className="hover:text-white transition-colors">Features</Link>
            <Link to="/privacy" className="hover:text-white transition-colors">Privacy</Link>
            <Link to="/terms" className="hover:text-white transition-colors">Terms</Link>
            <Link to="/login" className="hover:text-white transition-colors">Sign in</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
