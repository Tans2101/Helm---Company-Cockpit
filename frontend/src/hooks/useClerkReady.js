import { useEffect, useState } from "react";
import { useAuth as useClerkAuth, useSession } from "@clerk/clerk-react";
import { CLERK_AUTH_OPTS } from "@/lib/clerkSession";

/** Clerk SDK load state with a timeout so the UI does not spin forever. */
export function useClerkReady(timeoutMs = 20000) {
  const { isLoaded: clerkLoaded } = useClerkAuth(CLERK_AUTH_OPTS);
  const { isLoaded: sessionLoaded } = useSession();
  const [timedOut, setTimedOut] = useState(false);

  const clerkReady = clerkLoaded && sessionLoaded;

  useEffect(() => {
    if (clerkReady) {
      setTimedOut(false);
      return undefined;
    }
    const t = setTimeout(() => setTimedOut(true), timeoutMs);
    return () => clearTimeout(t);
  }, [clerkReady, timeoutMs]);

  return { clerkReady, clerkTimedOut: timedOut && !clerkReady };
}
