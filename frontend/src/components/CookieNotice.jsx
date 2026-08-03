import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

const KEY = "helm_cookie_ok";

export default function CookieNotice() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(KEY)) setVisible(true);
    } catch {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    try {
      localStorage.setItem(KEY, "1");
    } catch { /* ignore */ }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      data-testid="cookie-notice"
      className="fixed bottom-0 inset-x-0 z-[100] p-4 md:p-5"
    >
      <div className="mx-auto max-w-3xl flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 rounded-xl border border-white/10 bg-[#141417]/95 backdrop-blur-xl px-4 py-3.5 shadow-2xl">
        <p className="flex-1 text-sm text-zinc-300 leading-relaxed">
          Helm uses cookies for sign-in sessions and basic preferences. See our{" "}
          <Link to="/privacy" className="text-gold hover:underline">Privacy Policy</Link>.
        </p>
        <button
          data-testid="cookie-accept-btn"
          onClick={dismiss}
          className="shrink-0 rounded-md bg-gold text-black text-sm font-medium px-4 py-2 transition-colors hover:bg-gold-hover"
        >
          Got it
        </button>
      </div>
    </div>
  );
}
