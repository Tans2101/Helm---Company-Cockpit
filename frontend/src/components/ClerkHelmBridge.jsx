import { useEffect, useRef } from "react";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

/** Exchange a Clerk session JWT for Helm's httpOnly session cookie. */
export default function ClerkHelmBridge() {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user, loading, checkAuth } = useAuth();
  const busy = useRef(false);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || loading || user || busy.current) return;
    busy.current = true;
    (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        await api.post("/auth/clerk", {}, { headers: { Authorization: `Bearer ${token}` } });
        await checkAuth();
      } catch (e) {
        console.error("Clerk → Helm session exchange failed", e);
      } finally {
        busy.current = false;
      }
    })();
  }, [isLoaded, isSignedIn, loading, user, getToken, checkAuth]);

  return null;
}
