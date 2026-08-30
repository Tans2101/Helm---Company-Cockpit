import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, setClerkTokenGetter } from "@/lib/api";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clerkTokenWithRetry(getToken, attempts = 8) {
  for (let i = 0; i < attempts; i += 1) {
    const token = await getToken({ skipCache: true });
    if (token) return token;
    await sleep(250 * (i + 1));
  }
  return null;
}

/** Sync Clerk session → Helm user via /auth/me (Bearer JWT, not cookies). */
export default function ClerkHelmBridge() {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user, loading, setUser, setSessionError, clearSessionError } = useAuth();
  const navigate = useNavigate();
  const busy = useRef(false);

  useEffect(() => {
    setClerkTokenGetter(async () => {
      if (!isSignedIn) return null;
      return getToken({ skipCache: true });
    });
    return () => setClerkTokenGetter(null);
  }, [isSignedIn, getToken]);

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
        const { data } = await api.get("/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setUser(data);
        clearSessionError();
        navigate("/app", { replace: true });
      } catch (e) {
        const detail = e?.response?.data?.detail;
        setSessionError(
          typeof detail === "string"
            ? detail
            : `Sign-in failed (${e?.response?.status || "network"}). Try signing out and back in.`,
        );
        console.error("Clerk → Helm auth failed", e?.response?.data || e);
      } finally {
        busy.current = false;
      }
    })();
  }, [isLoaded, isSignedIn, loading, user, getToken, setUser, setSessionError, clearSessionError, navigate]);

  return null;
}
