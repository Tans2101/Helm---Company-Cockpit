import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { setClerkTokenGetter } from "@/lib/api";

/** Sync Clerk session → Helm user via /auth/me (accepts Clerk JWT bearer). */
export default function ClerkHelmBridge() {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user, loading, checkAuth, setSessionError } = useAuth();
  const navigate = useNavigate();
  const busy = useRef(false);

  useEffect(() => {
    setClerkTokenGetter(() => (isSignedIn ? getToken({ skipCache: false }) : null));
    return () => setClerkTokenGetter(null);
  }, [isSignedIn, getToken]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || loading || user || busy.current) return;
    busy.current = true;
    (async () => {
      try {
        await checkAuth();
        navigate("/app", { replace: true });
      } catch (e) {
        const detail = e?.response?.data?.detail;
        setSessionError(
          typeof detail === "string"
            ? detail
            : "Sign-in failed — check Render CLERK_SECRET_KEY matches your Clerk publishable key.",
        );
        console.error("Clerk → Helm auth failed", e);
      } finally {
        busy.current = false;
      }
    })();
  }, [isLoaded, isSignedIn, loading, user, checkAuth, setSessionError, navigate]);

  return null;
}
