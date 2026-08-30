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

/** Always use production pk_live for Helm — ignore test keys and wrong apps. */
export function getClerkPublishableKey() {
  const env = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();
  if (!env || env.startsWith("pk_test_")) {
    return HELM_CLERK_PUBLISHABLE_KEY;
  }
  const domain = domainFromPublishableKey(env);
  if (!domain || domain === "clerk.apexcoach.tech") {
    return HELM_CLERK_PUBLISHABLE_KEY;
  }
  if (domain === "causal-caribou-2352.clerk.accounts.dev" && env.startsWith("pk_live_")) {
    return env;
  }
  return HELM_CLERK_PUBLISHABLE_KEY;
}
