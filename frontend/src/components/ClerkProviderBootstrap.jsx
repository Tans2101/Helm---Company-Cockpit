import { createContext, useContext, useEffect, useState } from "react";
import { ClerkProvider } from "@clerk/clerk-react";
import { fetchAuthConfig } from "@/lib/api";
import { getClerkPublishableKey } from "@/lib/clerkConfig";
import { clerkPostAuthUrl, helmAppUrl } from "@/lib/helmUrls";

function clerkProxyUrl() {
  if (typeof window === "undefined") return undefined;
  const host = window.location.hostname;
  if (!host.endsWith("helmcontrol.online") && !host.endsWith("vercel.app")) return undefined;
  // Clerk requires proxy on primary apex domain, not www.
  if (host.endsWith("helmcontrol.online")) return "https://helmcontrol.online/__clerk";
  return `${window.location.origin.replace(/\/$/, "")}/__clerk`;
}

const ClerkModeContext = createContext({
  ready: false,
  configLoading: true,
  clerkEnabled: false,
  configError: null,
  postAuthUrl: null,
  helmCanonicalOrigin: null,
  clerkPrimaryOrigin: null,
  clerkMultiDomain: false,
});

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
 * Clerk redirect URLs use clerk_post_auth_url (apexcoach.tech) when multi-domain.
 */
export default function ClerkProviderBootstrap({ children }) {
  const [state, setState] = useState({
    ready: false,
    clerkEnabled: false,
    publishableKey: null,
    configError: null,
    postAuthUrl: null,
    helmCanonicalOrigin: null,
    clerkPrimaryOrigin: null,
    clerkMultiDomain: false,
    clerkUseProxy: false,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback = getClerkPublishableKey();
      try {
        const cfg = await fetchAuthConfig();
        if (cancelled) return;

        const postAuthUrl = (cfg?.clerk_post_auth_url || "").trim() || null;

        if (cfg?.clerk_enabled && cfg?.clerk_keys_aligned === false) {
          setState({
            ready: true,
            clerkEnabled: false,
            publishableKey: null,
            configError:
              "Clerk publishable key does not match the API JWKS instance. Fix CLERK_PUBLISHABLE_KEY on Render.",
            postAuthUrl,
            helmCanonicalOrigin: cfg?.helm_canonical_origin || null,
            clerkPrimaryOrigin: cfg?.clerk_primary_origin || null,
            clerkMultiDomain: Boolean(cfg?.clerk_multi_domain),
            clerkUseProxy: Boolean(cfg?.clerk_use_proxy),
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
            postAuthUrl,
            helmCanonicalOrigin: cfg?.helm_canonical_origin || null,
            clerkPrimaryOrigin: cfg?.clerk_primary_origin || null,
            clerkMultiDomain: Boolean(cfg?.clerk_multi_domain),
            clerkUseProxy: Boolean(cfg?.clerk_use_proxy),
          });
          return;
        }

        setState({
          ready: true,
          clerkEnabled: clerkOn && Boolean(key),
          publishableKey: key || null,
          configError: null,
          postAuthUrl,
          helmCanonicalOrigin: cfg?.helm_canonical_origin || null,
          clerkPrimaryOrigin: cfg?.clerk_primary_origin || null,
          clerkMultiDomain: Boolean(cfg?.clerk_multi_domain),
          clerkUseProxy: Boolean(cfg?.clerk_use_proxy),
        });
      } catch {
        if (cancelled) return;
        if (fallback) {
          setState({
            ready: true,
            clerkEnabled: true,
            publishableKey: fallback,
            configError: null,
            postAuthUrl: null,
            helmCanonicalOrigin: null,
            clerkPrimaryOrigin: null,
            clerkMultiDomain: false,
            clerkUseProxy: false,
          });
          return;
        }
        setState({
          ready: true,
          clerkEnabled: false,
          publishableKey: null,
          configError: "Could not reach the API to load sign-in configuration.",
          postAuthUrl: null,
          helmCanonicalOrigin: null,
          clerkPrimaryOrigin: null,
          clerkMultiDomain: false,
          clerkUseProxy: false,
        });
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const mode = {
    ready: state.ready,
    configLoading: !state.ready,
    clerkEnabled: state.clerkEnabled,
    configError: null,
    postAuthUrl: state.postAuthUrl,
    helmCanonicalOrigin: state.helmCanonicalOrigin,
    clerkPrimaryOrigin: state.clerkPrimaryOrigin,
    clerkMultiDomain: state.clerkMultiDomain,
  };

  if (state.configError) {
    return <ConfigErrorScreen message={state.configError} />;
  }

  const redirectUrl = clerkPostAuthUrl(state.postAuthUrl);

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
        {...(state.clerkUseProxy ? { proxyUrl: clerkProxyUrl() } : {})}
        signInUrl="/login"
        signUpUrl="/sign-up"
        signInForceRedirectUrl={redirectUrl}
        signUpForceRedirectUrl={redirectUrl}
        signInFallbackRedirectUrl={redirectUrl}
        signUpFallbackRedirectUrl={redirectUrl}
        afterSignOutUrl={helmAppUrl("/")}
      >
        {children}
      </ClerkProvider>
    </ClerkModeContext.Provider>
  );
}
