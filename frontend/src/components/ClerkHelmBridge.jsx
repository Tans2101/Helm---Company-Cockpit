import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth, useSession } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, setClerkTokenGetter } from "@/lib/api";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function resolveClerkToken(getToken, session) {
  for (let i = 0; i < 10; i += 1) {
    const fromSession = session ? await session.getToken({ skipCache: true }) : null;
    const fromAuth = await getToken({ skipCache: true });
    const token = fromSession || fromAuth;
    if (token && token.split(".").length === 3) return token;
    await sleep(300);
  }
  return null;
}

/** Sync Clerk session → Helm user via POST /auth/clerk/exchange */
export default function ClerkHelmBridge() {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { session } = useSession();
  const { user, setUser, setSessionError, clearSessionError } = useAuth();
  const navigate = useNavigate();
  const exchangedFor = useRef(null);

  useEffect(() => {
    setClerkTokenGetter(async () => {
      if (!isSignedIn) return null;
      return resolveClerkToken(getToken, session);
    });
    return () => setClerkTokenGetter(null);
  }, [isSignedIn, getToken, session]);

  useEffect(() => {
    if (!isSignedIn) {
      exchangedFor.current = null;
    }
  }, [isSignedIn]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || user) return;
    const sessionId = session?.id;
    if (!sessionId || exchangedFor.current === sessionId) return;

    let cancelled = false;
    (async () => {
      try {
        const token = await resolveClerkToken(getToken, session);
        if (!token) {
          if (!cancelled) {
            setSessionError("Clerk session not ready — wait a moment, then refresh.");
          }
          return;
        }
        exchangedFor.current = sessionId;
        let data;
        try {
          ({ data } = await api.post(
            "/auth/clerk/exchange",
            {},
            { headers: { Authorization: `Bearer ${token}` } },
          ));
        } catch (exchangeErr) {
          if (exchangeErr?.response?.status !== 404) throw exchangeErr;
          ({ data } = await api.get("/auth/me", {
            headers: { Authorization: `Bearer ${token}` },
          }));
        }
        if (cancelled) return;
        setUser(data);
        clearSessionError();
        if (!window.location.pathname.startsWith("/app")) {
          navigate("/app", { replace: true });
        }
      } catch (e) {
        exchangedFor.current = null;
        if (cancelled) return;
        const detail = e?.response?.data?.detail;
        setSessionError(
          typeof detail === "string"
            ? detail
            : `Sign-in failed (${e?.response?.status || "network"}).`,
        );
        console.error("Clerk Helm sync failed", e?.response?.data || e);
      }
    })();

    return () => { cancelled = true; };
  }, [
    isLoaded, isSignedIn, user, session?.id, getToken, session,
    setUser, setSessionError, clearSessionError, navigate,
  ]);

  return null;
}
