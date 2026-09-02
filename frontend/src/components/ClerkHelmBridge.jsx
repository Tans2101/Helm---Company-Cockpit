import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth, useSession } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useClerkMode } from "@/components/ClerkProviderBootstrap";
import { useAuth } from "@/context/AuthContext";
import { api, setClerkTokenGetter } from "@/lib/api";
import { resolveClerkToken } from "@/lib/clerkToken";
import { clerkSessionActive, CLERK_AUTH_OPTS } from "@/lib/clerkSession";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function exchangeClerkSession(token) {
  try {
    const { data } = await api.post(
      "/auth/clerk/exchange",
      {},
      { headers: { Authorization: `Bearer ${token}` } },
    );
    return data;
  } catch (exchangeErr) {
    if (exchangeErr?.response?.status === 404) {
      const { data } = await api.get("/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      return data;
    }
    throw exchangeErr;
  }
}

/** Sync Clerk session → Helm user via POST /auth/clerk/exchange */
export default function ClerkHelmBridge() {
  const {
    isLoaded, isSignedIn, getToken, userId, sessionId, sessionStatus,
  } = useClerkAuth(CLERK_AUTH_OPTS);
  const { session, isLoaded: sessionLoaded } = useSession();
  const { user, setUser, setSessionError, clearSessionError } = useAuth();
  const { helmCanonicalOrigin, clerkPrimaryOrigin, clerkMultiDomain } = useClerkMode();
  const navigate = useNavigate();
  const syncing = useRef(false);

  const clerkReady = isLoaded && sessionLoaded;
  const clerkActive = clerkSessionActive({
    isSignedIn, userId, sessionId, session, sessionStatus,
  });

  useEffect(() => {
    setClerkTokenGetter(async () => {
      if (!clerkActive) return null;
      return resolveClerkToken(getToken, session);
    });
    return () => setClerkTokenGetter(null);
  }, [clerkActive, getToken, session]);

  useEffect(() => {
    if (!clerkReady || !clerkActive || user || syncing.current) return;
    // OAuth can return before Clerk finalizes the session JWT — wait for active status.
    if (sessionStatus === "pending") return;

    let cancelled = false;
    syncing.current = true;

    (async () => {
      clearSessionError();
      for (let attempt = 0; attempt < 40 && !cancelled; attempt += 1) {
        try {
          const token = await resolveClerkToken(getToken, session);
          if (!token) {
            await sleep(500);
            continue;
          }
          const data = await exchangeClerkSession(token);
          if (cancelled) return;
          setUser(data);
          clearSessionError();
          // Clerk may redirect to apexcoach.tech; send user to helmcontrol after session exchange.
          if (
            clerkMultiDomain
            && helmCanonicalOrigin
            && clerkPrimaryOrigin
            && typeof window !== "undefined"
          ) {
            const here = window.location.origin.replace(/\/$/, "");
            const clerkOrigin = clerkPrimaryOrigin.replace(/\/$/, "");
            const canon = helmCanonicalOrigin.replace(/\/$/, "");
            if (here === clerkOrigin && canon !== clerkOrigin) {
              window.location.replace(`${canon}/app`);
              return;
            }
          }
          if (!window.location.pathname.startsWith("/app")) {
            navigate("/app", { replace: true });
          }
          return;
        } catch (e) {
          const status = e?.response?.status;
          if (status === 503 && attempt < 39) {
            await sleep(1500);
            continue;
          }
          if (attempt < 5 && (status >= 500 || !status)) {
            await sleep(1000);
            continue;
          }
          if (cancelled) return;
          const detail = e?.response?.data?.detail;
          setSessionError(
            typeof detail === "string"
              ? detail
              : `Sign-in failed (${status || "network"}).`,
          );
          console.error("Clerk Helm sync failed", e?.response?.data || e);
          return;
        }
      }
      if (!cancelled) {
        setSessionError("Clerk session not ready — wait a moment, then refresh.");
      }
    })().finally(() => {
      syncing.current = false;
    });

    return () => { cancelled = true; };
  }, [
    clerkReady, clerkActive, user, session?.id, sessionId, userId, sessionStatus,
    getToken, session, setUser, setSessionError, clearSessionError, navigate,
    clerkMultiDomain, clerkPrimaryOrigin, helmCanonicalOrigin,
  ]);

  return null;
}
