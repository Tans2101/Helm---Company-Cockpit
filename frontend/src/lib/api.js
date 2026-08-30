import axios from "axios";

/** Empty string = same-origin `/api` (Vercel rewrite → Render). Local: http://localhost:8001 */
export const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

let clerkGetToken = null;

/** Register Clerk getToken so every API call can send the session JWT. */
export function setClerkTokenGetter(getter) {
  clerkGetToken = getter;
}

api.interceptors.request.use(async (config) => {
  if (!clerkGetToken) return config;
  try {
    const token = await clerkGetToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    /* Clerk not ready */
  }
  return config;
});

/** Fetch auth config without Clerk token (bootstrap). */
export async function fetchAuthConfig() {
  const { data } = await axios.get(`${API}/auth/config`, { withCredentials: true });
  return data;
}
