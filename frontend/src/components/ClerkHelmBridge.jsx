import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { setClerkTokenGetter } from "@/lib/api";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clerkTokenWithRetry(getToken, attempts = 6) {
  for (let i = 0; i < attempts; i += 1) {
    const token = await getToken({ skipCache: true });
    if (token) return token;
    await sleep(200 * (i + 1));
  }
  return null;
}

/** Sync Clerk session → Helm user via /auth/me (accepts Clerk JWT bearer). */
export default function ClerkHelmBridge() {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user, loading, checkAuth, setSessionError } = useAuth();
  const navigate = useNavigate();
  const busy = useRef(false);

  useEffect(() => {
    setClerkTokenGetter(async () => {
      if (!isSignedIn) return null;
      return getToken({ skipCache: true });
    });
    return () => setClerkTokenGetter(null);
  }, [isSignedIn, getToken]);

  // Cookie session for returning users not signed in to Clerk this tab.
  useEffect(() => {
    if (!isLoaded || isSignedIn || user) return;
    checkAuth().catch(() => {});
  }, [isLoaded, isSignedIn, user, checkAuth]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || loading || user || busy.current) return;
    busy.current = true;
    (async () => {
      try {
        const token = await clerkTokenWithRetry(getToken);
        if (!token) {
          setSessionError("Clerk session not ready — refresh and try again.");
          return;
        }
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
  }, [isLoaded, isSignedIn, loading, user, getToken, checkAuth, setSessionError, navigate]);

  return null;
}
