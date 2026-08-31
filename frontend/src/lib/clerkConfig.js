/** Build-time fallback — ClerkProviderBootstrap overrides from /api/auth/config when set. */
export const HELM_CLERK_PUBLISHABLE_KEY =
  (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();

/** Publishable key from Vercel build env (apexcoach.tech Clerk instance). */
export function getClerkPublishableKey() {
  return HELM_CLERK_PUBLISHABLE_KEY;
}
