/** Helm production Clerk instance (must match Render CLERK_JWKS_URL / causal-caribou-2352). */
export const HELM_CLERK_PUBLISHABLE_KEY =
  "pk_live_Y2F1c2FsLWNhcmlib3UtMjM1Mi5jbGVyay5hY2NvdW50cy5kZXYk";

function domainFromPublishableKey(key) {
  if (!key) return null;
  try {
    const encoded = key.replace(/^pk_(live|test)_/, "");
    return atob(encoded).replace(/\$$/, "");
  } catch {
    return null;
  }
}

/** Build-time fallback — ClerkProviderBootstrap may override from /api/auth/config. */
export function getClerkPublishableKey() {
  const env = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();
  if (env && domainFromPublishableKey(env) !== "clerk.apexcoach.tech") {
    return env;
  }
  return HELM_CLERK_PUBLISHABLE_KEY;
}
