import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children, onLogoutExtra }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState("");

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      setSessionError("");
    } catch (e) {
      setUser(null);
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
    checkAuth();
  }, [checkAuth]);

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
