/** Absolute Helm URLs for Clerk redirects (must be full URL, not relative). */
export function helmOrigin() {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return (process.env.REACT_APP_HELM_ORIGIN || "").trim();
}

export function helmAppUrl(path = "/app") {
  const origin = helmOrigin();
  return origin ? `${origin}${path}` : path;
}

/** Clerk post-auth redirect — must use Clerk primary domain (e.g. apexcoach.tech). */
export function clerkPostAuthUrl(fallback) {
  return fallback || helmAppUrl("/app");
}
