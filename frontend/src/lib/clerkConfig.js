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

/** Use env key unless it points at the wrong Clerk app (e.g. apexcoach). */
export function getClerkPublishableKey() {
  const env = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();
  const domain = domainFromPublishableKey(env);
  if (!env || domain === "clerk.apexcoach.tech") {
    return HELM_CLERK_PUBLISHABLE_KEY;
  }
  if (domain === "causal-caribou-2352.clerk.accounts.dev") {
    return env;
  }
  return env || HELM_CLERK_PUBLISHABLE_KEY;
}
