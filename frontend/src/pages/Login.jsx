import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && user) navigate("/app", { replace: true });
  }, [user, loading, navigate]);

  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/app";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#09090b] grain">
      {/* Left: brand / pitch */}
      <div className="relative flex flex-col justify-between p-10 md:p-16 border-r border-white/5 z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
            <span className="font-mono text-gold font-medium">H</span>
          </div>
          <div>
            <p className="text-white font-semibold tracking-tight leading-none">Helm</p>
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mt-1">CEO Operating System</p>
          </div>
        </div>

        <div className="max-w-lg">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-6">Quiet control</p>
          <h1 className="text-4xl md:text-6xl font-light tracking-tight text-white leading-[1.05]">
            Run your company from one command center.
          </h1>
          <p className="text-zinc-400 text-base md:text-lg mt-6 leading-relaxed">
            Helm pulls status and KPIs in, pushes work out, and answers the only question that matters —
            <span className="text-white"> what does the CEO need to know right now?</span>
          </p>
          <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-zinc-500">
            <span>Morning briefing</span>
            <span className="text-zinc-700">·</span>
            <span>Decision center</span>
            <span className="text-zinc-700">·</span>
            <span>Runway & burn</span>
            <span className="text-zinc-700">·</span>
            <span>Ask Helm</span>
          </div>
        </div>

        <p className="text-xs text-zinc-700">Know what matters before your first meeting.</p>
      </div>

      {/* Right: auth */}
      <div className="flex items-center justify-center p-10 relative z-10">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-normal text-white tracking-tight">Enter the cockpit</h2>
          <p className="text-zinc-500 text-sm mt-2">Sign in to your executive command center.</p>

          <button
            data-testid="google-login-btn"
            onClick={handleLogin}
            className="group mt-8 w-full flex items-center justify-center gap-3 rounded-lg bg-gold text-black font-medium py-3 transition-colors hover:bg-gold-hover"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="currentColor" d="M12.24 10.4v3.28h4.56c-.2 1.18-1.4 3.46-4.56 3.46-2.75 0-4.99-2.28-4.99-5.09s2.24-5.09 4.99-5.09c1.56 0 2.61.67 3.21 1.24l2.19-2.11C16.36 3.9 14.5 3.1 12.24 3.1 7.9 3.1 4.4 6.6 4.4 10.94s3.5 7.84 7.84 7.84c4.53 0 7.53-3.18 7.53-7.66 0-.51-.06-.9-.13-1.29h-7.4z"/>
            </svg>
            Continue with Google
            <ArrowRight className="w-4 h-4 opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
          </button>

          <div className="mt-6 flex items-center gap-2 text-xs text-zinc-600">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Secure sign-in. Your data stays private to you.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
