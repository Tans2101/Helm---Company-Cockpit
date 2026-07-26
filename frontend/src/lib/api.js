import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status;
    const onAuthFlow = typeof window !== "undefined" && (
      window.location.pathname === "/login" ||
      window.location.hash?.includes("session_id=")
    );
    if (status === 401 && !onAuthFlow && typeof window !== "undefined") {
      // Session expired mid-app — send them back to login once.
      if (!window.__helmAuthRedirecting) {
        window.__helmAuthRedirecting = true;
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);
