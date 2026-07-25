import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export function useFetch(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.get(path)
      .then((r) => { if (mounted) setData(r.data); })
      .catch((e) => { if (mounted) setError(e); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, reloadKey, ...deps]);

  const reload = () => setReloadKey((k) => k + 1);
  return { data, loading, error, reload, setData };
}
