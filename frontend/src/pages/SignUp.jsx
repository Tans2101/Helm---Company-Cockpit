import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SignUp, useAuth as useClerkAuth, useClerk } from "@clerk/clerk-react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { getClerkPublishableKey } from "@/lib/clerkConfig";
import { clerkAppearance } from "@/lib/clerkTheme";
import { LoadingScreen } from "@/components/kit";

const CLERK_KEY = getClerkPublishableKey();

export default function SignUpPage() {
  const { user, loading, sessionError, clearSessionError } = useAuth();
  const { isLoaded: clerkLoaded, isSignedIn } = useClerkAuth();
  const { signOut } = useClerk();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && user) navigate("/app", { replace: true });
  }, [user, loading, navigate]);

  if (!clerkLoaded || loading) {
    return <LoadingScreen label="Loading sign-up" />;
  }

  if (isSignedIn && !user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8">
        <LoadingScreen label={sessionError ? "Sign-up problem" : "Finishing sign-up"} />
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
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-6">Join Helm</p>
          <h1 className="text-4xl md:text-6xl font-light tracking-tight text-white leading-[1.05]">
            Your company command center awaits.
          </h1>
        </div>
        <p className="text-xs text-zinc-700">
          Already have an account?{" "}
          <Link to="/login" className="text-gold hover:underline">Sign in</Link>
        </p>
      </div>

      <div className="flex items-center justify-center p-10 relative z-10">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-normal text-white tracking-tight">Create your account</h2>
          <p className="text-zinc-500 text-sm mt-2">Google or email — password rules are set in Clerk.</p>

          {CLERK_KEY ? (
            <div className="mt-6" data-testid="clerk-sign-up">
              <SignUp
                appearance={clerkAppearance}
                routing="virtual"
                signInUrl="/login"
                forceRedirectUrl={`${window.location.origin}/app`}
                fallbackRedirectUrl={`${window.location.origin}/app`}
              />
            </div>
          ) : (
            <p className="mt-8 text-sm text-rose-400">Clerk is not configured.</p>
          )}

          <div className="mt-6 flex items-center gap-2 text-xs text-zinc-600">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Powered by Clerk</span>
          </div>
        </div>
      </div>
    </div>
  );
}
