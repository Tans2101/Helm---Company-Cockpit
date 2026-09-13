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
      <div className="mx-auto max-w-3xl flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 rounded-xl border border-helm-line bg-helm-card px-4 py-3.5 shadow-2xl">
        <p className="flex-1 text-sm text-helm-fg leading-relaxed">
          Helm uses a session cookie to keep you signed in, a small preference to remember this notice,
          and cookieless Vercel Analytics for page views. No advertising cookies. Details in our{" "}
          <Link to="/privacy" className="text-helm-gold hover:underline">Privacy Policy</Link>.
        </p>
        <button
          data-testid="cookie-accept-btn"
          onClick={dismiss}
          className="shrink-0 rounded-md bg-helm-gold text-helm-navy text-sm font-medium px-4 py-2 transition-colors hover:bg-helm-gold-hover"
        >
          Got it
        </button>
      </div>
    </div>
  );
}
