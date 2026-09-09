import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const STORAGE_KEY = "helm_appearance";
const ThemeContext = createContext(null);
const VALID = new Set(["light", "dark", "system"]);

function savedTheme() {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return VALID.has(value) ? value : "light";
  } catch {
    return "light";
  }
}

function systemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function writeLocal(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Theme still applies in this tab when storage is unavailable.
  }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(savedTheme);
  const [system, setSystem] = useState(systemTheme);
  const resolvedTheme = theme === "system" ? system : theme;

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: light)");
    if (!query) return undefined;
    const update = (event) => setSystem(event.matches ? "light" : "dark");
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);

  const hydrateAppearance = useCallback((value) => {
    if (!VALID.has(value)) return;
    setThemeState(value);
    writeLocal(value);
  }, []);

  const setTheme = useCallback(async (value, { persistRemote = true } = {}) => {
    if (!VALID.has(value)) return;
    setThemeState(value);
    writeLocal(value);
    if (!persistRemote) return;
    try {
      await api.patch("/account/appearance", { appearance: value });
    } catch {
      // Local preference still applies; remote sync retries on next change after auth.
    }
  }, []);

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme, hydrateAppearance }),
    [theme, resolvedTheme, setTheme, hydrateAppearance],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
