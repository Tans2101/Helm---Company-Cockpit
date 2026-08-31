/** Absolute Helm URLs for Clerk redirects (must be full URL, not relative). */
export function helmOrigin() {
  if (typeof window === "undefined") return "";
  return window.location.origin;
}

export function helmAppUrl(path = "/app") {
  const origin = helmOrigin();
  return origin ? `${origin}${path}` : path;
}
