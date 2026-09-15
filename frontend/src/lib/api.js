import axios from "axios";

/** Empty string = same-origin `/api` (Vercel rewrite → Render). Local: http://localhost:8001 */
export const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
  timeout: 20000,
});

let clerkGetToken = null;

const BOOTSTRAP_PATHS = ["/auth/me", "/auth/config"];

/** Register Clerk getToken so every API call can send the session JWT. */
export function setClerkTokenGetter(getter) {
  clerkGetToken = getter;
}

api.interceptors.request.use(async (config) => {
  config.headers = config.headers || {};
  // Caller already attached a Bearer token (e.g. Clerk exchange) — don't override/block.
  if (config.headers.Authorization) return config;
  if (!clerkGetToken) return config;
  const url = config.url || "";
  if (BOOTSTRAP_PATHS.some((p) => url.includes(p))) return config;
  try {
    // getCachedClerkToken already bounds Clerk refreshes and falls back to a
    // still-valid JWT. Do not wrap another short Promise.race here — a 1.5s
    // outer timeout was aborting legitimate refreshes (session + getToken can
    // each take up to 1.5s) and surfacing as "Could not save" on Financials.
    const token = await clerkGetToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      return config;
    }
    // No token yet — fail instead of sending an unauthenticated call that 401s
    // and flips soft-reload pages into ErrorScreen.
    return Promise.reject(new Error("clerk-token-timeout"));
  } catch (err) {
    const msg = err?.message || "clerk-token-timeout";
    return Promise.reject(new Error(msg === "clerk-token-timeout" ? msg : "clerk-token-timeout"));
  }
});

/** Fetch auth config without Clerk token (bootstrap). */
export async function fetchAuthConfig() {
  const { data } = await axios.get(`${API}/auth/config`, { withCredentials: true });
  return data;
}
