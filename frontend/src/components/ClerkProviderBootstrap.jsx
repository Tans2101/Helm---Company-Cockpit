import { createContext, useContext, useEffect, useState } from "react";
import { ClerkProvider } from "@clerk/clerk-react";
import { fetchAuthConfig } from "@/lib/api";
import { getClerkPublishableKey } from "@/lib/clerkConfig";
import { helmAppUrl } from "@/lib/helmUrls";
import { LoadingScreen } from "@/components/kit";

const ClerkModeContext = createContext({ ready: false, clerkEnabled: false, configError: null });

/** Whether Clerk auth is active (from /api/auth/config, not build-time env). */
export function useClerkMode() {
  return useContext(ClerkModeContext);
}

function ConfigErrorScreen({ message }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8 text-center">
      <p className="text-lg text-white mb-2">Sign-in configuration problem</p>
      <p className="text-sm text-rose-400 max-w-md">{message}</p>
      <button
        type="button"
        className="mt-6 text-sm text-gold hover:underline"
        onClick={() => window.location.reload()}
      >
        Retry
      </button>
    </div>
  );
}

/**
 * Load publishable key from /api/auth/config (matches CLERK_SECRET_KEY + JWKS on Render).
 * Falls back to REACT_APP_CLERK_PUBLISHABLE_KEY only in local test mode.
 */
export default function ClerkProviderBootstrap({ children }) {
  const [state, setState] = useState({
    ready: false,
    clerkEnabled: false,
    publishableKey: null,
    configError: null,
  });
  const appUrl = helmAppUrl("/app");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback = getClerkPublishableKey();
      try {
        const cfg = await fetchAuthConfig();
        if (cancelled) return;

        if (cfg?.clerk_enabled && cfg?.clerk_keys_aligned === false) {
          setState({
            ready: true,
            clerkEnabled: false,
            publishableKey: null,
            configError:
              "Clerk publishable key does not match the API JWKS instance. Fix CLERK_PUBLISHABLE_KEY on Render.",
          });
          return;
        }

        const fromApi = (cfg?.clerk_publishable_key || "").trim();
        const clerkOn = Boolean(cfg?.clerk_enabled);
        let key = "";
        if (fromApi) {
          key = fromApi;
        } else if (cfg?.clerk_secret_mode === "test") {
          const env = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();
          if (env.startsWith("pk_test_")) key = env;
        }
        if (!key && clerkOn) {
          setState({
            ready: true,
            clerkEnabled: false,
            publishableKey: null,
            configError: "Clerk is enabled on the API but no publishable key is configured.",
          });
          return;
        }

        setState({
          ready: true,
          clerkEnabled: clerkOn && Boolean(key),
          publishableKey: key || null,
          configError: null,
        });
      } catch {
        if (cancelled) return;
        if (fallback) {
          setState({
            ready: true,
            clerkEnabled: true,
            publishableKey: fallback,
            configError: null,
          });
          return;
        }
        setState({
          ready: true,
          clerkEnabled: false,
          publishableKey: null,
          configError: "Could not reach the API to load sign-in configuration.",
        });
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!state.ready) {
    return <LoadingScreen label="Loading sign-in" />;
  }

  if (state.configError) {
    return <ConfigErrorScreen message={state.configError} />;
  }

  const mode = { ready: true, clerkEnabled: state.clerkEnabled, configError: null };

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
