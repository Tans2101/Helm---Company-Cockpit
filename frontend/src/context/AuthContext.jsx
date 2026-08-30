import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children, onLogoutExtra, deferInitialAuth = false }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState("");

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      setSessionError("");
      return data;
    } catch (e) {
      setUser(null);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearSessionError = useCallback(() => setSessionError(""), []);

  useEffect(() => {
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    if (deferInitialAuth) {
      setLoading(false);
      if (window.location.pathname.startsWith("/app")) {
        api.get("/auth/me")
          .then(({ data }) => { setUser(data); setSessionError(""); })
          .catch(() => {});
      }
      return;
    }
    checkAuth().catch(() => {});
  }, [checkAuth, deferInitialAuth]);

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) {}
    setUser(null);
    setSessionError("");
    if (onLogoutExtra) {
      try { await onLogoutExtra(); } catch (e) {}
    }
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{
      user, setUser, loading, checkAuth, logout, sessionError, setSessionError, clearSessionError,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
