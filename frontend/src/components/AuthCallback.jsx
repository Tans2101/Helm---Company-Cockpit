import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

export default function AuthCallback() {
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const hash = window.location.hash || "";
    const sid = new URLSearchParams(hash.replace(/^#/, "")).get("session_id");
    (async () => {
      let dest = "/app";
      try {
        if (sid) await api.post("/auth/session", { session_id: sid });
        const { data } = await api.get("/auth/me");
        if (data?.default_route) dest = data.default_route;
      } catch (e) {
        // ignore, redirect will re-check
      }
      window.location.replace(dest);
    })();
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b]">
      <div className="w-8 h-8 rounded-full border-2 border-gold/30 border-t-gold animate-spin mb-6" />
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Helm</p>
      <p className="text-zinc-500 text-sm mt-2">Know what matters before your first meeting</p>
    </div>
  );
}
