import data from "./seoPages.json";

export const HELM_ORIGIN = data.origin;
export const DEFAULT_OG_IMAGE = data.ogImage;
export const SEO_PAGES = data.pages;
export const MARKETING_SEO_PATHS = Object.keys(SEO_PAGES);

export function seoForPath(pathname) {
  const path = (pathname || "/").replace(/\/$/, "") || "/";
  return SEO_PAGES[path] || null;
}

export function canonicalForPath(pathname) {
  const path = (pathname || "/").replace(/\/$/, "") || "/";
  if (path.startsWith("/app")) return `${HELM_ORIGIN}/`;
  if (SEO_PAGES[path]) return path === "/" ? `${HELM_ORIGIN}/` : `${HELM_ORIGIN}${path}`;
  if (path === "/") return `${HELM_ORIGIN}/`;
  return `${HELM_ORIGIN}${path}`;
}
