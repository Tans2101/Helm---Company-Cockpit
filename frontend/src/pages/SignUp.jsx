import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SignUp, useAuth as useClerkAuth, useSession, useClerk } from "@clerk/clerk-react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useClerkMode } from "@/components/ClerkProviderBootstrap";
import { clerkAppearance } from "@/lib/clerkTheme";
import { LoadingScreen } from "@/components/kit";
import ClerkLoadError from "@/components/ClerkLoadError";
import { useClerkReady } from "@/hooks/useClerkReady";
import { clerkSessionComplete, CLERK_AUTH_OPTS } from "@/lib/clerkSession";
import { clerkAfterAuthRedirect } from "@/lib/clerkRedirect";
import { helmSignInUrl } from "@/lib/helmUrls";
import { TAGLINE, CATEGORY } from "@/lib/marketingCopy";
import AuthMarketingHeader from "@/components/marketing/AuthMarketingHeader";

export default function SignUpPage() {
  const { clerkEnabled, configLoading } = useClerkMode();
  if (configLoading) {
    return <LoadingScreen label="Loading sign-up" />;
  }
  if (!clerkEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-helm-ink p-8">
        <p className="text-sm text-helm-status-negative">Sign-up is not available. Clerk is not configured on this deployment.</p>
      </div>
    );
  }
  return <SignUpClerk />;
}

function SignUpClerk() {
  const { postAuthUrl, helmCanonicalOrigin, clerkMultiDomain, passwordMinLength, captchaEnabled } = useClerkMode();
  const redirectUrl = clerkAfterAuthRedirect({ clerkMultiDomain, postAuthUrl });
  const signInPath = helmSignInUrl(helmCanonicalOrigin);
  const { user, loading, sessionError, clearSessionError } = useAuth();
  const { isSignedIn, userId, sessionId, sessionStatus } = useClerkAuth(CLERK_AUTH_OPTS);
  const { session } = useSession();
  const { signOut } = useClerk();
  const navigate = useNavigate();
  const { clerkReady, clerkTimedOut } = useClerkReady();

  const clerkComplete = clerkSessionComplete({ isSignedIn, userId, sessionId, session, sessionStatus });

  useEffect(() => {
    if (!loading && user) navigate("/app", { replace: true });
  }, [user, loading, navigate]);

  useEffect(() => {
    if (!clerkReady || user) return;
    if (clerkComplete) navigate("/app", { replace: true });
  }, [clerkReady, clerkComplete, user, navigate]);

  if (clerkTimedOut) {
    return <ClerkLoadError />;
  }

  if (!clerkReady || loading) {
    return <LoadingScreen label="Loading sign-up" />;
  }

  if (clerkComplete && !user) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-helm-ink p-8">
        <LoadingScreen label={sessionError ? "Sign-up problem" : "Finishing sign-up"} />
        {sessionError && (
          <div className="mt-6 max-w-md text-center space-y-4">
            <p className="text-sm text-helm-status-negative">{sessionError}</p>
            <button
              type="button"
              className="text-sm text-helm-gold hover:underline"
              onClick={async () => {
                clearSessionError();
                await signOut();
                window.location.href = "/sign-up";
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
    <div className="min-h-screen grid lg:grid-cols-2 bg-helm-ink grain relative">
      <AuthMarketingHeader />
      <div className="relative flex flex-col justify-between p-10 md:p-16 pt-28 lg:pt-16 border-r border-helm-cream/5 z-10">
        <div className="max-w-lg flex-1 flex flex-col justify-center">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-helm-gold mb-6">{CATEGORY}</p>
          <h1 className="font-display text-4xl md:text-6xl font-normal tracking-tight text-helm-cream leading-[1.05]">
            {TAGLINE}
          </h1>
          <p className="text-helm-slate text-base md:text-lg mt-6 leading-relaxed">
            Create your account and set up your workspace. Start on Free, or upgrade anytime. Paid plans include a 7-day trial.
          </p>
        </div>
        <p className="text-xs text-helm-muted">
          Already have an account?{" "}
          <Link to="/login" className="text-helm-gold hover:underline">Sign in</Link>
        </p>
      </div>

      <div className="flex items-center justify-center p-10 relative z-10">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-normal text-helm-cream tracking-tight">Create your account</h2>
          <p className="text-helm-slate text-sm mt-2">Google or email. Activate Trenston after sign-up.</p>
          {passwordMinLength > 8 && (
            <p className="mt-3 text-sm text-helm-gold/90">
              Email sign-up needs a password of at least {passwordMinLength} characters
              {captchaEnabled ? " (Clerk also shows a CAPTCHA)" : ""}. Google skips the password.
            </p>
          )}

          <div className="mt-6" data-testid="clerk-sign-up">
            <SignUp
              appearance={clerkAppearance}
              routing="path"
              path="/sign-up"
              signInUrl={signInPath}
              oauthFlow="auto"
              forceRedirectUrl={redirectUrl}
              fallbackRedirectUrl={redirectUrl}
              signInForceRedirectUrl={redirectUrl}
              signInFallbackRedirectUrl={redirectUrl}
            />
          </div>

          <div className="mt-6 flex items-center gap-2 text-xs text-helm-slate">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Powered by Clerk</span>
          </div>
          <p className="mt-4 text-center text-xs text-helm-slate">
            <Link to="/" className="hover:text-helm-slate transition-colors">← Back to home</Link>
            <span className="mx-2 text-helm-muted">·</span>
            <Link to="/privacy" className="hover:text-helm-slate transition-colors">Privacy</Link>
            <span className="mx-2 text-helm-muted">·</span>
            <Link to="/security" className="hover:text-helm-slate transition-colors">Security</Link>
            <span className="mx-2 text-helm-muted">·</span>
            <Link to="/terms" className="hover:text-helm-slate transition-colors">Terms</Link>
            <span className="mx-2 text-helm-muted">·</span>
            <Link to="/refunds" className="hover:text-helm-slate transition-colors">Refunds</Link>
            <span className="mx-2 text-helm-muted">·</span>
            <Link to="/login" className="hover:text-helm-slate transition-colors">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
