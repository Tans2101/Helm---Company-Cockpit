import { useEffect, useState } from "react";
import { ClerkProvider } from "@clerk/clerk-react";
import { fetchAuthConfig } from "@/lib/api";
import { getClerkPublishableKey } from "@/lib/clerkConfig";
import { helmAppUrl } from "@/lib/helmUrls";
import { LoadingScreen } from "@/components/kit";

/**
 * Load publishable key from Render /api/auth/config when set (matches CLERK_SECRET_KEY mode).
 * Falls back to build-time key from vercel.json / REACT_APP_CLERK_PUBLISHABLE_KEY.
 */
export default function ClerkProviderBootstrap({ children }) {
  const [publishableKey, setPublishableKey] = useState(null);
  const appUrl = helmAppUrl("/app");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback = getClerkPublishableKey();
      try {
        const cfg = await fetchAuthConfig();
        if (cancelled) return;
        const fromApi = (cfg?.clerk_publishable_key || "").trim();
        if (fromApi) {
          setPublishableKey(fromApi);
          return;
        }
        if (cfg?.clerk_secret_mode === "test") {
          const env = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();
          if (env.startsWith("pk_test_")) {
            setPublishableKey(env);
            return;
          }
        }
        setPublishableKey(fallback);
      } catch {
        if (!cancelled) setPublishableKey(fallback);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!publishableKey) {
    return <LoadingScreen label="Loading sign-in" />;
  }

  return (
    <ClerkProvider
      publishableKey={publishableKey}
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
  );
}
