import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export function useFetch(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!path) { setLoading(false); return; }
    let mounted = true;
    setLoading(true);
    setError(null);
    api.get(path)
      .then((r) => {
        if (!mounted) return;
        setData(r.data);
        setError(null);
      })
      .catch((e) => { if (mounted) setError(e); })
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
  if (error?.code === "ECONNABORTED") return "Request timed out. The server may be busy — try again.";
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
