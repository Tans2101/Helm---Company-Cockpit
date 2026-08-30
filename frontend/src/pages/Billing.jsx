import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, Sparkles, ArrowLeft, ShieldCheck, ExternalLink, AlertTriangle } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { initPaddle } from "@/lib/paddle";
import { GlassCard, SectionLabel, LoadingScreen } from "@/components/kit";

const FREE = ["Baseline dashboard & KPIs", "Limited AI (5 messages/day)", "Manual task board", "Read-only reports"];
const PRO = [
  "AI Morning Briefing & synthesis",
  "Full Decision Center with recommendations",
  "Weekly CEO Pack (AI-generated)",
  "Live integrations (Google, QuickBooks, GitHub)",
  "Unlimited Ask Helm",
  "Scenario planning & risk matrix",
];

export default function Billing() {
  const { data, loading } = useFetch("/billing/plans");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (loading || !data) return <LoadingScreen label="Loading plans" />;
  const isPro = data.current_plan === "pro";
  const proPrice = data.pro_price ?? data.price ?? 8;
  const pastDue = data.subscription_status === "past_due";

  const upgradePaddle = async () => {
    if (!data.paddle_ready) {
      toast.error("Paddle checkout is not configured");
      return;
    }
    setBusy(true);
    try {
      const { data: cfg } = await api.post("/billing/paddle/config");
      const Paddle = await initPaddle(cfg.client_token, cfg.environment, (ev) => {
        if (ev?.name === "checkout.completed") {
          toast.success("Payment received — activating Pro…");
          setTimeout(() => window.location.reload(), 4500);
        }
      });
      Paddle.Checkout.open({
        settings: { displayMode: "overlay", theme: "dark" },
        items: [{ priceId: cfg.price_id, quantity: 1 }],
        customData: { workspace_id: cfg.workspace_id, user_id: cfg.user_id, checkout_nonce: cfg.checkout_nonce },
        ...(cfg.email ? { customer: { email: cfg.email } } : {}),
      });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start Paddle checkout");
    } finally {
      setBusy(false);
    }
  };

  const openPortal = async () => {
    setBusy(true);
    try {
      const { data: res } = await api.post("/payments/paddle/portal");
      if (res?.url) window.location.href = res.url;
      else toast.error("Could not open billing portal");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not open billing portal");
    } finally {
      setBusy(false);
    }
  };

  const resetDemo = async () => {
    try {
      await api.post("/demo/reset-plan");
      toast.success("Reverted to Free (demo)");
      setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Demo reset is disabled");
    }
  };

  return (
    <div className="max-w-4xl">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-white mb-6 transition-colors" data-testid="billing-back">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      {pastDue && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200" data-testid="past-due-banner">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-100">Payment past due</p>
            <p className="text-amber-200/80 mt-0.5">Update your payment method to keep Pro access.</p>
            {data.portal_available && (
              <button onClick={openPortal} disabled={busy} className="mt-2 text-xs font-medium text-amber-100 underline hover:no-underline">
                Manage billing
              </button>
            )}
          </div>
        </div>
      )}

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
            ) : data.demo_reset_enabled ? (
              <button onClick={resetDemo} data-testid="reset-demo-btn" className="w-full border border-white/10 text-zinc-400 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors">Revert to Free (demo)</button>
            ) : null}
          </div>
        </GlassCard>

        <GlassCard glow className="p-6 fade-up border-gold/30 relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-gold text-black text-[10px] font-mono uppercase tracking-wider px-3 py-1 rounded-bl-lg">Recommended</div>
          <div className="flex items-center gap-2">
            <SectionLabel>Pro</SectionLabel>
            <Sparkles className="w-3.5 h-3.5 text-gold" />
          </div>
          <p className="font-mono text-4xl text-white mt-3">${proPrice}<span className="text-base text-zinc-600">/mo</span></p>
          <p className="text-sm text-zinc-500 mt-1">The full command center.</p>
          <div className="mt-6 space-y-3">
            {PRO.map((f) => (
              <div key={f} className="flex items-center gap-2.5 text-sm text-zinc-200">
                <Check className="w-4 h-4 text-gold shrink-0" /> {f}
              </div>
            ))}
          </div>
          <div className="mt-6 space-y-2">
            {isPro ? (
              <>
                <div className="text-center text-xs font-mono uppercase tracking-wide text-gold border border-gold/30 bg-gold/10 rounded-md py-2.5" data-testid="pro-active">Active — you're on Pro</div>
                {data.portal_available && (
                  <button data-testid="manage-billing-btn" onClick={openPortal} disabled={busy}
                    className="w-full flex items-center justify-center gap-2 border border-white/10 text-zinc-300 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors disabled:opacity-60">
                    <ExternalLink className="w-4 h-4" /> Manage billing
                  </button>
                )}
              </>
            ) : (
              <button data-testid="upgrade-checkout-btn" onClick={upgradePaddle} disabled={busy || !data.paddle_ready}
                className="w-full bg-gold text-black font-medium rounded-md py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">
                {busy ? "Starting checkout…" : `Upgrade to Pro — $${proPrice}/mo`}
              </button>
            )}
            {!isPro && data.paddle_ready && (
              <div className="flex items-center justify-center gap-1.5 text-[11px] text-zinc-600 mt-1">
                <ShieldCheck className="w-3.5 h-3.5 text-gold/70" /> Secure checkout by Paddle
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      <p className="text-center text-[11px] text-zinc-600 mt-8 leading-relaxed">
        Payments processed by Paddle (Merchant of Record). Subscriptions renew automatically each billing period until you cancel
        in the Paddle customer portal. Cancel anytime.{" "}
        <Link to="/terms" className="text-zinc-500 hover:text-zinc-300 transition-colors">Terms</Link>
        {" · "}
        <Link to="/privacy" className="text-zinc-500 hover:text-zinc-300 transition-colors">Privacy</Link>
      </p>
    </div>
  );
}
