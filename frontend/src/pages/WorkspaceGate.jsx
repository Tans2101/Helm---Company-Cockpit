import { useState } from "react";
import { toast } from "sonner";
import { Building2, KeyRound, ArrowRight, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { GlassCard } from "@/components/kit";

export default function WorkspaceGate() {
  const { user, logout } = useAuth();
  const [mode, setMode] = useState(null); // "create" | "join"
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const create = async () => {
    if (!name.trim()) { toast.error("Name your company"); return; }
    setBusy(true);
    try {
      await api.post("/workspaces", { name: name.trim() });
      window.location.href = "/app";
    } catch (e) { toast.error("Could not create company"); setBusy(false); }
  };

  const join = async () => {
    if (!code.trim()) { toast.error("Enter your invite code"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/workspaces/join", { code: code.trim() });
      if (data.ok) window.location.href = "/app";
    } catch (e) { toast.error(e?.response?.data?.detail || "Invalid invite code"); setBusy(false); }
  };

  return (
    <div className="min-h-screen grain flex flex-col items-center justify-center px-5 py-12">
      <div className="w-full max-w-xl">
        <div className="flex items-center justify-between mb-10">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
              <span className="font-mono text-gold font-medium">H</span>
            </div>
            <div>
              <p className="text-white font-semibold tracking-tight leading-none">Helm</p>
              <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mt-1">Company Workspace</p>
            </div>
          </div>
          <button data-testid="gate-logout" onClick={logout} className="text-zinc-500 hover:text-white flex items-center gap-1.5 text-sm"><LogOut className="w-4 h-4" /> Sign out</button>
        </div>

        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Welcome, {user?.name?.split(" ")[0] || "there"}</p>
        <h1 className="mt-3 text-3xl md:text-4xl font-light tracking-tight text-white">Join your company on Helm.</h1>
        <p className="mt-3 text-zinc-500">If your team already uses Helm, join with an invite code. Starting fresh? Create your company.</p>

        {!mode && (
          <div className="mt-10 grid sm:grid-cols-2 gap-4 fade-up">
            <button data-testid="gate-join-choice" onClick={() => setMode("join")}
              className="text-left rounded-xl border border-white/10 bg-white/[0.02] p-6 transition-colors hover:border-gold/40 group">
              <div className="w-11 h-11 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center"><KeyRound className="w-5 h-5 text-gold" /></div>
              <h3 className="mt-4 text-lg text-white tracking-tight">Join with a code</h3>
              <p className="mt-1.5 text-sm text-zinc-500 leading-relaxed">Enter the invite code your admin shared, or use your email invite link.</p>
              <span className="mt-4 inline-flex items-center gap-1.5 text-sm text-gold">Enter code <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" /></span>
            </button>
            <button data-testid="gate-create-choice" onClick={() => setMode("create")}
              className="text-left rounded-xl border border-white/10 bg-white/[0.02] p-6 transition-colors hover:border-gold/40 group">
              <div className="w-11 h-11 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center"><Building2 className="w-5 h-5 text-gold" /></div>
              <h3 className="mt-4 text-lg text-white tracking-tight">Create a company</h3>
              <p className="mt-1.5 text-sm text-zinc-500 leading-relaxed">Name your company now — you'll set up the rest (stage, team, industry) on the next screen.</p>
              <span className="mt-4 inline-flex items-center gap-1.5 text-sm text-gold">Get started <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" /></span>
            </button>
          </div>
        )}

        {mode === "join" && (
          <GlassCard className="mt-10 p-6 fade-up">
            <label className="text-xs text-zinc-500">Invite code
              <input data-testid="gate-code-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Paste your invite code"
                onKeyDown={(e) => e.key === "Enter" && join()}
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 font-mono focus:outline-none focus:border-gold/40" />
            </label>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setMode(null)} className="rounded-md border border-white/10 text-zinc-300 text-sm px-4 py-2.5 hover:bg-white/5">Back</button>
              <button data-testid="gate-join-btn" onClick={join} disabled={busy} className="flex-1 rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60">{busy ? "Joining…" : "Join company"}</button>
            </div>
          </GlassCard>
        )}

        {mode === "create" && (
          <GlassCard className="mt-10 p-6 fade-up">
            <label className="text-xs text-zinc-500">Company name
              <input data-testid="gate-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Inc."
                onKeyDown={(e) => e.key === "Enter" && create()}
                className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40" />
            </label>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setMode(null)} className="rounded-md border border-white/10 text-zinc-300 text-sm px-4 py-2.5 hover:bg-white/5">Back</button>
              <button data-testid="gate-create-btn" onClick={create} disabled={busy} className="flex-1 rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60">{busy ? "Creating…" : "Create company"}</button>
            </div>
          </GlassCard>
        )}
      </div>
    </div>
  );
}
