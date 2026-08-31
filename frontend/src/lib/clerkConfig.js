/** Build-time fallback — production loads pk_* from /api/auth/config on Render. */
export const HELM_CLERK_PUBLISHABLE_KEY =
  (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();

/** Optional local-dev publishable key; must match Render CLERK_JWKS_URL instance. */
export function getClerkPublishableKey() {
  return HELM_CLERK_PUBLISHABLE_KEY;
}
