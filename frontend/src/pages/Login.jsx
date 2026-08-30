import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SignIn, useAuth as useClerkAuth, useClerk } from "@clerk/clerk-react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getClerkPublishableKey } from "@/lib/clerkConfig";
import { clerkAppearance } from "@/lib/clerkTheme";
import { LoadingScreen } from "@/components/kit";

const CLERK_KEY = getClerkPublishableKey();

export default function Login() {
  const { user, loading, sessionError, clearSessionError } = useAuth();
  const { isLoaded: clerkLoaded, isSignedIn } = useClerkAuth();
  const { signOut } = useClerk();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && user) navigate("/app", { replace: true });
  }, [user, loading, navigate]);

  useEffect(() => {
    if (clerkLoaded && isSignedIn && !user && !loading && !sessionError) {
      navigate("/app", { replace: true });
    }
  }, [clerkLoaded, isSignedIn, user, loading, sessionError, navigate]);

  if (!clerkLoaded || loading) {
    return <LoadingScreen label="Loading sign-in" />;
  }

  if (isSignedIn && !user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8">
        <LoadingScreen label={sessionError ? "Sign-in problem" : "Finishing sign-in"} />
        {sessionError && (
          <div className="mt-6 max-w-md text-center space-y-4">
            <p className="text-sm text-rose-400">{sessionError}</p>
            <button
              type="button"
              className="text-sm text-gold hover:underline"
              onClick={async () => {
                clearSessionError();
                await signOut();
              }}
            >
              Sign out and try again
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#09090b] grain">
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
        </div>

        <p className="text-xs text-zinc-700">Know what matters before your first meeting.</p>
      </div>

      <div className="flex items-center justify-center p-10 relative z-10">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-normal text-white tracking-tight">Enter the cockpit</h2>
          <p className="text-zinc-500 text-sm mt-2">Sign in to your executive command center.</p>

          {CLERK_KEY ? (
            <div className="mt-6" data-testid="clerk-sign-in">
              <SignIn
                appearance={clerkAppearance}
                routing="path"
                path="/login"
                signUpUrl="/login"
                forceRedirectUrl={`${window.location.origin}/app`}
                fallbackRedirectUrl={`${window.location.origin}/app`}
              />
            </div>
          ) : (
            <p className="mt-8 text-sm text-rose-400">Clerk is not configured on this deployment.</p>
          )}

          <p className="mt-4 text-center text-xs text-zinc-600">
            <Link to="/privacy" className="hover:text-zinc-400 transition-colors">Privacy</Link>
            <span className="mx-2 text-zinc-700">·</span>
            <Link to="/terms" className="hover:text-zinc-400 transition-colors">Terms</Link>
          </p>

          <div className="mt-6 flex items-center gap-2 text-xs text-zinc-600">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Sign-in powered by Clerk — same account always returns to your company.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
