import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";

export function useFetch(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const prevPathRef = useRef(path);

  useEffect(() => {
    if (!path) {
      setData(null);
      setError(null);
      setLoading(false);
      prevPathRef.current = path;
      return;
    }
    let mounted = true;
    const pathChanged = prevPathRef.current !== path;
    prevPathRef.current = path;

    if (pathChanged) {
      // Different resource — never show the previous path's data.
      setData(null);
      setLoading(true);
    } else {
      // Soft reload of the same path: keep showing existing rows.
      setLoading((prev) => (data == null ? true : prev));
    }
    setError(null);

    api.get(path)
      .then((r) => {
        if (!mounted) return;
        setData(r.data);
        setError(null);
      })
      .catch((e) => {
        if (!mounted) return;
        // Soft reload: keep prior data and don't flip the whole page to ErrorScreen.
        if (pathChanged) {
          setError(e);
        } else {
          setError((prev) => (data == null ? e : prev));
        }
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, reloadKey, ...deps]);

  const reload = () => setReloadKey((k) => k + 1);
  return { data, loading, error, reload, setData };
}

export function fetchErrorMessage(error, fallback = "Could not load data. Check your connection and try again.") {
  if (!error) return fallback;
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg || String(d)).join(", ");
  if (error?.message === "clerk-token-timeout") return "Sign-in is still loading. Wait a moment and try again.";
  if (error?.code === "ECONNABORTED") return "Request timed out. The server may be busy. Try again.";
  return error?.message || fallback;
}

/** Parse API error detail when responseType was blob (e.g. CSV download). */
export async function blobErrorDetail(error, fallback = "Request failed") {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string") return parsed.detail;
    } catch {
      /* ignore */
    }
  }
  return fetchErrorMessage(error, fallback);
}
