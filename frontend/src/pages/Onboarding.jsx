import { useState } from "react";
import { toast } from "sonner";
import { Sparkles, PenLine, ArrowRight, Check } from "lucide-react";
import { api } from "@/lib/api";
import { GlassCard } from "@/components/kit";

export default function Onboarding() {
  const [busy, setBusy] = useState(null);

  const choose = async (template) => {
    setBusy(template);
    try {
      await api.post("/workspace/apply-template", { template });
      window.location.href = "/app";
    } catch (e) {
      toast.error("Something went wrong. Please try again.");
      setBusy(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 fade-up">
      <div className="text-center">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Welcome to Helm</p>
        <h1 className="mt-4 text-3xl md:text-4xl font-light tracking-tight text-white">Let's set up your cockpit.</h1>
        <p className="mt-3 text-zinc-500 max-w-md mx-auto">Explore with a fully-loaded sample company, or start clean and bring in your own data.</p>
      </div>

      <div className="mt-12 grid md:grid-cols-2 gap-5">
        <GlassCard className="p-7 flex flex-col">
          <div className="w-11 h-11 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-gold" />
          </div>
          <h3 className="mt-5 text-xl text-white tracking-tight">Explore with sample data</h3>
          <p className="mt-2 text-sm text-zinc-500 leading-relaxed flex-1">
            Load "Northwind Robotics" — a realistic Series A company with financials, decisions, tasks and a team. See exactly how Helm works in 10 seconds.
          </p>
          <ul className="mt-4 space-y-1.5">
            {["6 months of financials", "Live briefing & decisions", "Full team & telemetry"].map((f) => (
              <li key={f} className="flex items-center gap-2 text-xs text-zinc-400"><Check className="w-3.5 h-3.5 text-gold" />{f}</li>
            ))}
          </ul>
          <button data-testid="onboarding-sample-btn" onClick={() => choose("sample")} disabled={!!busy}
            className="group mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-gold text-black font-medium py-2.5 transition-colors hover:bg-gold-hover disabled:opacity-60">
            {busy === "sample" ? "Loading…" : "Explore sample"}
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </button>
        </GlassCard>

        <GlassCard className="p-7 flex flex-col">
          <div className="w-11 h-11 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center">
            <PenLine className="w-5 h-5 text-gold" />
          </div>
          <h3 className="mt-5 text-xl text-white tracking-tight">Start clean</h3>
          <p className="mt-2 text-sm text-zinc-500 leading-relaxed flex-1">
            Begin with an empty cockpit and make it yours. Log your financials, invite your team, and connect your tools — Helm builds your command center around real data.
          </p>
          <ul className="mt-4 space-y-1.5">
            {["Log financials in Helm", "Invite your finance team", "Connect Google, QuickBooks & more"].map((f) => (
              <li key={f} className="flex items-center gap-2 text-xs text-zinc-400"><Check className="w-3.5 h-3.5 text-zinc-600" />{f}</li>
            ))}
          </ul>
          <button data-testid="onboarding-clean-btn" onClick={() => choose("clean")} disabled={!!busy}
            className="mt-6 inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 text-white font-medium py-2.5 transition-colors hover:bg-white/5 disabled:opacity-60">
            {busy === "clean" ? "Setting up…" : "Start clean"}
          </button>
        </GlassCard>
      </div>
    </div>
  );
}
