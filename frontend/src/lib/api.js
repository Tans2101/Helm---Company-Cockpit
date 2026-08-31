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
  if (!clerkGetToken) return config;
  const url = config.url || "";
  if (BOOTSTRAP_PATHS.some((p) => url.includes(p))) return config;
  try {
    const token = await Promise.race([
      clerkGetToken(),
      new Promise((_, reject) => setTimeout(() => reject(new Error("clerk-token-timeout")), 4000)),
    ]);
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    /* Clerk not ready — do not block API calls */
  }
  return config;
});

/** Fetch auth config without Clerk token (bootstrap). */
export async function fetchAuthConfig() {
  const { data } = await axios.get(`${API}/auth/config`, { withCredentials: true });
  return data;
}
