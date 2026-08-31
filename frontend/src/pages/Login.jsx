import { useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { SignIn, useAuth as useClerkAuth, useSession, useClerk } from "@clerk/clerk-react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useClerkMode } from "@/components/ClerkProviderBootstrap";
import { clerkAppearance } from "@/lib/clerkTheme";
import { LoadingScreen } from "@/components/kit";
import { clerkSessionActive, CLERK_AUTH_OPTS } from "@/lib/clerkSession";
import { clerkPostAuthUrl } from "@/lib/helmUrls";

export default function Login() {
  const { clerkEnabled } = useClerkMode();
  if (!clerkEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#09090b] p-8">
        <p className="text-sm text-rose-400">Sign-in is not available — Clerk is not configured on this deployment.</p>
      </div>
    );
  }
  return <LoginClerk />;
}

function LoginClerk() {
  const { postAuthUrl } = useClerkMode();
  const redirectUrl = clerkPostAuthUrl(postAuthUrl);
  const [searchParams] = useSearchParams();
  const urlError = searchParams.get("error");
  const { user, loading, sessionError, clearSessionError } = useAuth();
  const { isLoaded: clerkLoaded, isSignedIn, userId, sessionId, sessionStatus } = useClerkAuth(CLERK_AUTH_OPTS);
  const { session, isLoaded: sessionLoaded } = useSession();
  const { signOut } = useClerk();
  const navigate = useNavigate();

  const clerkReady = clerkLoaded && sessionLoaded;
  const clerkActive = clerkSessionActive({ isSignedIn, userId, sessionId, session, sessionStatus });

  useEffect(() => {
    if (!loading && user) navigate("/app", { replace: true });
  }, [user, loading, navigate]);

  useEffect(() => {
    if (!clerkReady || user) return;
    if (clerkActive) navigate("/app", { replace: true });
  }, [clerkReady, clerkActive, user, navigate]);

  if (!clerkReady || loading) {
    return <LoadingScreen label="Loading sign-in" />;
  }

  if (clerkActive && !user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8 text-center">
        <LoadingScreen label={sessionError ? "Sign-in problem" : "Finishing sign-in"} />
        {sessionError && (
          <div className="mt-6 max-w-md space-y-4">
            <p className="text-sm text-rose-400">{sessionError}</p>
            <button
              type="button"
              className="text-sm text-gold hover:underline"
              onClick={async () => {
                clearSessionError();
                await signOut();
                window.location.href = "/login";
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
          <p className="text-zinc-500 text-sm mt-2">Sign in with Google or email.</p>

          {urlError === "session_retired" && (
            <p className="mt-4 text-sm text-amber-400">That sign-in link has expired. Please sign in again below.</p>
          )}

          <div className="mt-6" data-testid="clerk-sign-in">
            <SignIn
              appearance={clerkAppearance}
              routing="path"
              path="/login"
              signUpUrl="/sign-up"
              oauthFlow="redirect"
              forceRedirectUrl={redirectUrl}
              fallbackRedirectUrl={redirectUrl}
            />
          </div>

          <p className="mt-4 text-center text-xs text-zinc-600">
            <Link to="/privacy" className="hover:text-zinc-400 transition-colors">Privacy</Link>
            <span className="mx-2 text-zinc-700">·</span>
            <Link to="/terms" className="hover:text-zinc-400 transition-colors">Terms</Link>
            <span className="mx-2 text-zinc-700">·</span>
            <Link to="/sign-up" className="hover:text-gold transition-colors">Create account</Link>
          </p>

          <p className="mt-3 text-center text-xs text-zinc-500">
            Password rules are set in Clerk (not Helm). Use Google for fastest sign-in.
          </p>

          <div className="mt-6 flex items-center gap-2 text-xs text-zinc-600">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Sign-in powered by Clerk</span>
          </div>
        </div>
      </div>
    </div>
  );
}
