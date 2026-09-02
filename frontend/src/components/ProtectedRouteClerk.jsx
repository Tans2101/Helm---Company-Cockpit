import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth as useClerkAuth, useSession, useClerk } from "@clerk/clerk-react";
import { useAuth } from "@/context/AuthContext";
import AppLayout from "@/components/AppLayout";
import WorkspaceGate from "@/pages/WorkspaceGate";
import { LoadingScreen } from "@/components/kit";
import ClerkLoadError from "@/components/ClerkLoadError";
import { useClerkReady } from "@/hooks/useClerkReady";
import { clerkSessionActive, CLERK_AUTH_OPTS } from "@/lib/clerkSession";

/** Protected routes when Clerk is enabled — wait for Clerk→Helm session exchange. */
export default function ProtectedRouteClerk() {
  const { user, sessionError, clearSessionError } = useAuth();
  const {
    isSignedIn,
    userId,
    sessionId,
    sessionStatus,
  } = useClerkAuth(CLERK_AUTH_OPTS);
  const { session } = useSession();
  const { signOut } = useClerk();
  const { clerkReady, clerkTimedOut } = useClerkReady();
  const [connectTimedOut, setConnectTimedOut] = useState(false);

  const clerkActive = clerkSessionActive({
    isSignedIn, userId, sessionId, session, sessionStatus,
  });

  useEffect(() => {
    if (user || !clerkActive || sessionError) {
      setConnectTimedOut(false);
      return undefined;
    }
    const t = setTimeout(() => setConnectTimedOut(true), 25000);
    return () => clearTimeout(t);
  }, [user, clerkActive, sessionError]);

  if (clerkTimedOut) {
    return <ClerkLoadError />;
  }

  if (!clerkReady) {
    return <LoadingScreen label="Loading cockpit" />;
  }

  if (user) {
    if (user.needs_workspace) return <WorkspaceGate />;
    return <AppLayout />;
  }

  if (clerkActive) {
    if (sessionError || connectTimedOut) {
      const message = sessionError || "Connecting your account is taking too long. Try again.";
      return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8 text-center">
          <p className="text-lg text-white mb-2">Could not connect your account</p>
          <p className="text-sm text-rose-400 max-w-md mb-6">{message}</p>
          <button
            type="button"
            className="rounded-lg bg-gold text-black px-4 py-2 text-sm font-medium"
            onClick={async () => {
              clearSessionError();
              setConnectTimedOut(false);
              await signOut();
              window.location.href = "/login";
            }}
          >
            Sign out and try again
          </button>
        </div>
      );
    }
    return <LoadingScreen label="Connecting your account" />;
  }

  return <Navigate to="/login" replace />;
}
