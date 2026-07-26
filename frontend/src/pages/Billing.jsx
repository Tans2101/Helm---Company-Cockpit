import { useState } from "react";
import { toast } from "sonner";
import { Check, Sparkles, ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { GlassCard, SectionLabel, LoadingScreen, ErrorScreen } from "@/components/kit";

const FREE = ["Baseline dashboard & KPIs", "Limited AI (5 messages/day)", "Manual task board", "Read-only reports"];
const PRO = [
  "AI Morning Briefing & synthesis",
  "Full Decision Center with recommendations",
  "Weekly CEO Pack (AI-generated)",
  "Live integrations (Google, Stripe, QuickBooks, GitHub)",
  "Unlimited Ask Helm",
  "Scenario planning & risk matrix",
];

export default function Billing() {
  const { data, loading, error, reload } = useFetch("/billing/plans");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (loading) return <LoadingScreen label="Loading plans" />;
  if (error || !data) return <ErrorScreen onRetry={reload} />;
  const isPro = data.current_plan === "pro";
  const canManage = !!data.can_manage;

  const upgrade = async () => {
    if (!canManage) {
      toast.error("Only a workspace owner can manage billing");
      return;
    }
    setBusy(true);
    try {
      const { data: res } = await api.post("/payments/checkout", { origin_url: window.location.origin });
      window.location.href = res.checkout_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start checkout");
      setBusy(false);
    }
  };

  const resetDemo = async () => {
    if (!canManage) {
      toast.error("Only a workspace owner can manage billing");
      return;
    }
    try {
      await api.post("/demo/reset-plan");
      toast.success("Reverted to Free (demo)");
      setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not reset plan");
    }
  };

  return (
    <div className="max-w-4xl">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-white mb-6 transition-colors" data-testid="billing-back">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <div className="text-center mb-10 fade-up">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">Plans</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">Run your company from one command center.</h1>
        <p className="text-zinc-500 mt-3">Upgrade to unlock the full CEO Operating System.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <GlassCard className="p-6 fade-up">
          <SectionLabel>Free</SectionLabel>
          <p className="font-mono text-4xl text-white mt-3">$0<span className="text-base text-zinc-600">/mo</span></p>
          <p className="text-sm text-zinc-500 mt-1">Baseline cockpit + limited AI.</p>
          <div className="mt-6 space-y-3">
            {FREE.map((f) => (
              <div key={f} className="flex items-center gap-2.5 text-sm text-zinc-400">
                <Check className="w-4 h-4 text-zinc-600 shrink-0" /> {f}
              </div>
            ))}
          </div>
          <div className="mt-6">
            {!isPro ? (
              <div className="text-center text-xs font-mono uppercase tracking-wide text-zinc-600 border border-white/10 rounded-md py-2.5">Current plan</div>
            ) : canManage ? (
              <button onClick={resetDemo} data-testid="reset-demo-btn" className="w-full border border-white/10 text-zinc-400 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors">Revert to Free (demo)</button>
            ) : (
              <div className="text-center text-xs font-mono uppercase tracking-wide text-zinc-600 border border-white/10 rounded-md py-2.5">Pro active</div>
            )}
          </div>
        </GlassCard>

        <GlassCard glow className="p-6 fade-up border-gold/30 relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-gold text-black text-[10px] font-mono uppercase tracking-wider px-3 py-1 rounded-bl-lg">Recommended</div>
          <div className="flex items-center gap-2">
            <SectionLabel>Pro</SectionLabel>
            <Sparkles className="w-3.5 h-3.5 text-gold" />
          </div>
          <p className="font-mono text-4xl text-white mt-3">${data.pro_price}<span className="text-base text-zinc-600">/mo</span></p>
          <p className="text-sm text-zinc-500 mt-1">The full command center.</p>
          <div className="mt-6 space-y-3">
            {PRO.map((f) => (
              <div key={f} className="flex items-center gap-2.5 text-sm text-zinc-200">
                <Check className="w-4 h-4 text-gold shrink-0" /> {f}
              </div>
            ))}
          </div>
          <div className="mt-6">
            {isPro ? (
              <div className="text-center text-xs font-mono uppercase tracking-wide text-gold border border-gold/30 bg-gold/10 rounded-md py-2.5" data-testid="pro-active">Active — you're on Pro</div>
            ) : canManage ? (
              <button data-testid="upgrade-checkout-btn" onClick={upgrade} disabled={busy}
                className="w-full bg-gold text-black font-medium rounded-md py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">
                {busy ? "Starting checkout…" : `Upgrade to Pro — $${data.pro_price}/mo`}
              </button>
            ) : (
              <div className="text-center text-xs text-zinc-500 border border-white/10 rounded-md py-2.5 px-3">
                Ask a workspace owner to upgrade billing.
              </div>
            )}
            {canManage && !isPro && (
              <p className="text-center text-[11px] text-zinc-600 mt-3">Test mode · use card 4242 4242 4242 4242</p>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
