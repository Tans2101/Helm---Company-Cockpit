import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useClerkMode } from "@/components/ClerkProviderBootstrap";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { clerkSessionActive, CLERK_AUTH_OPTS } from "@/lib/clerkSession";

/** Auth state + enter handler for public marketing pages. */
export function useMarketingAuth() {
  const { user, loading } = useAuth();
  const { clerkEnabled } = useClerkMode();
  const navigate = useNavigate();

  if (clerkEnabled) {
    const { isLoaded: clerkLoaded, isSignedIn, userId, sessionId, sessionStatus } = useClerkAuth(CLERK_AUTH_OPTS);
    const clerkActive = clerkLoaded && clerkSessionActive({
      isSignedIn, userId, sessionId, session: null, sessionStatus,
    });
    const authed = !loading && (!!user || clerkActive);
    const enter = () => navigate(authed ? "/app" : "/sign-up");
    return { authed, enter, loading };
  }

  const authed = !loading && !!user;
  const enter = () => navigate(authed ? "/app" : "/sign-up");
  return { authed, enter, loading };
}
