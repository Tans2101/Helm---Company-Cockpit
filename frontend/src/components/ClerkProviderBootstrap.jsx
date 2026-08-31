import { createContext, useContext, useEffect, useState } from "react";
import { ClerkProvider } from "@clerk/clerk-react";
import { fetchAuthConfig } from "@/lib/api";
import { getClerkPublishableKey } from "@/lib/clerkConfig";
import { helmAppUrl } from "@/lib/helmUrls";
import { LoadingScreen } from "@/components/kit";

const ClerkModeContext = createContext({ ready: false, clerkEnabled: false });

/** Whether Clerk auth is active (from /api/auth/config, not build-time env). */
export function useClerkMode() {
  return useContext(ClerkModeContext);
}

/**
 * Load publishable key from /api/auth/config (matches CLERK_SECRET_KEY + JWKS on Render).
 * Falls back to REACT_APP_CLERK_PUBLISHABLE_KEY when the API has no key.
 */
export default function ClerkProviderBootstrap({ children }) {
  const [state, setState] = useState({ ready: false, clerkEnabled: false, publishableKey: null });
  const appUrl = helmAppUrl("/app");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback = getClerkPublishableKey();
      try {
        const cfg = await fetchAuthConfig();
        if (cancelled) return;
        const fromApi = (cfg?.clerk_publishable_key || "").trim();
        const clerkOn = Boolean(cfg?.clerk_enabled);
        const keysAligned = cfg?.clerk_keys_aligned !== false;

        let key = "";
        if (fromApi && keysAligned) {
          key = fromApi;
        } else if (cfg?.clerk_secret_mode === "test") {
          const env = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();
          if (env.startsWith("pk_test_")) key = env;
        }
        if (!key) key = fallback;

        setState({
          ready: true,
          clerkEnabled: clerkOn && Boolean(key),
          publishableKey: key || null,
        });
      } catch {
        if (!cancelled) {
          setState({
            ready: true,
            clerkEnabled: Boolean(fallback),
            publishableKey: fallback || null,
          });
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!state.ready) {
    return <LoadingScreen label="Loading sign-in" />;
  }

  const mode = { ready: true, clerkEnabled: state.clerkEnabled };

  if (!state.clerkEnabled || !state.publishableKey) {
    return (
      <ClerkModeContext.Provider value={mode}>
        {children}
      </ClerkModeContext.Provider>
    );
  }

  return (
    <ClerkModeContext.Provider value={mode}>
      <ClerkProvider
        publishableKey={state.publishableKey}
        signInUrl="/login"
        signUpUrl="/sign-up"
        signInForceRedirectUrl={appUrl}
        signUpForceRedirectUrl={appUrl}
        signInFallbackRedirectUrl={appUrl}
        signUpFallbackRedirectUrl={appUrl}
        afterSignOutUrl={helmAppUrl("/")}
      >
        {children}
      </ClerkProvider>
    </ClerkModeContext.Provider>
  );
}
