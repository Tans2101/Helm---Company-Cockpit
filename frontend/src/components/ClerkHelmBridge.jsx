import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth, useClerk } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

/** Exchange a Clerk session JWT for Helm's httpOnly session cookie. */
export default function ClerkHelmBridge() {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { signOut } = useClerk();
  const { user, loading, checkAuth, setSessionError } = useAuth();
  const navigate = useNavigate();
  const busy = useRef(false);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || loading || user || busy.current) return;
    busy.current = true;
    (async () => {
      try {
        let token = await getToken({ skipCache: true });
        if (!token) {
          await new Promise((r) => setTimeout(r, 400));
          token = await getToken({ skipCache: true });
        }
        if (!token) {
          setSessionError("Clerk session missing — please sign in again.");
          return;
        }
        await api.post("/auth/clerk", {}, { headers: { Authorization: `Bearer ${token}` } });
        await checkAuth();
        navigate("/app", { replace: true });
      } catch (e) {
        const detail = e?.response?.data?.detail;
        const message = typeof detail === "string"
          ? detail
          : "Could not finish sign-in. Try again or contact support.";
        setSessionError(message);
        try {
          await signOut();
        } catch {
          /* ignore */
        }
        navigate("/login", { replace: true });
        console.error("Clerk → Helm session exchange failed", e);
      } finally {
        busy.current = false;
      }
    })();
  }, [isLoaded, isSignedIn, loading, user, getToken, checkAuth, setSessionError, signOut, navigate]);

  return null;
}
