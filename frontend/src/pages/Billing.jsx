import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, Sparkles, ArrowLeft, ShieldCheck, ExternalLink, AlertTriangle } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { initPaddle } from "@/lib/paddle";
import { HELM_FEATURES } from "@/lib/marketingCopy";
import { GlassCard, SectionLabel, LoadingScreen, ErrorScreen } from "@/components/kit";

export default function Billing() {
  const { data, loading, error, reload } = useFetch("/billing/plans");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (loading) return <LoadingScreen label="Loading billing" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load billing"
        message={fetchErrorMessage(error, "Billing data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  const billingEnforced = data.billing_enforced === true;
  const isPro = billingEnforced ? data.current_plan === "pro" : true;
  const proPrice = data.pro_price ?? data.price ?? 8;
  const pastDue = billingEnforced && data.subscription_status === "past_due";

  const activatePaddle = async () => {
    if (!data.paddle_ready) {
      toast.error("Paddle checkout is not configured");
      return;
    }
    setBusy(true);
    try {
      const { data: cfg } = await api.post("/billing/paddle/config");
      const Paddle = await initPaddle(cfg.client_token, cfg.environment, (ev) => {
        if (ev?.name === "checkout.completed") {
          toast.success("Payment received — activating Helm…");
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
      toast.success("Reverted to inactive (demo)");
      setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Demo reset is disabled");
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-white mb-6 transition-colors" data-testid="billing-back">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      {pastDue && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200" data-testid="past-due-banner">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-100">Payment past due</p>
            <p className="text-amber-200/80 mt-0.5">Update your payment method to keep Helm access.</p>
            {data.portal_available && (
              <button onClick={openPortal} disabled={busy} className="mt-2 text-xs font-medium text-amber-100 underline hover:no-underline">
                Manage billing
              </button>
            )}
          </div>
        </div>
      )}

      {!billingEnforced && (
        <div className="mb-6 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200" data-testid="billing-standby-banner">
          <p className="font-medium text-emerald-100">Billing is paused</p>
          <p className="text-emerald-200/80 mt-0.5">Helm is free while you build and test. Set <code className="font-mono text-xs">BILLING_ENFORCED=true</code> on the API when you&apos;re ready to charge.</p>
        </div>
      )}

      <div className="text-center mb-10 fade-up">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">Helm</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">Activate your CEO Operating System.</h1>
        <p className="text-zinc-500 mt-3">One plan. Full cockpit. Cancel anytime.</p>
      </div>

      <GlassCard glow className="p-6 fade-up border-gold/30 relative overflow-hidden">
        <div className="flex items-center gap-2">
          <SectionLabel>Helm</SectionLabel>
          <Sparkles className="w-3.5 h-3.5 text-gold" />
        </div>
        <p className="font-mono text-4xl text-white mt-3">${proPrice}<span className="text-base text-zinc-600">/mo</span></p>
        <p className="text-sm text-zinc-500 mt-1">The full command center for seed & Series A CEOs.</p>
        <div className="mt-6 space-y-3">
          {HELM_FEATURES.map((f) => (
            <div key={f} className="flex items-center gap-2.5 text-sm text-zinc-200">
              <Check className="w-4 h-4 text-gold shrink-0" /> {f}
            </div>
          ))}
        </div>
        <div className="mt-6 space-y-2">
          {isPro ? (
            <>
              <div className="text-center text-xs font-mono uppercase tracking-wide text-gold border border-gold/30 bg-gold/10 rounded-md py-2.5" data-testid="pro-active">Active — Helm</div>
              {data.portal_available && (
                <button data-testid="manage-billing-btn" onClick={openPortal} disabled={busy}
                  className="w-full flex items-center justify-center gap-2 border border-white/10 text-zinc-300 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors disabled:opacity-60">
                  <ExternalLink className="w-4 h-4" /> Manage billing
                </button>
              )}
            </>
          ) : (
            <button data-testid="upgrade-checkout-btn" onClick={activatePaddle} disabled={busy || !data.paddle_ready}
              className="w-full bg-gold text-black font-medium rounded-md py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Starting checkout…" : `Activate Helm — $${proPrice}/mo`}
            </button>
          )}
          {!isPro && data.paddle_ready && (
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-zinc-600 mt-1">
              <ShieldCheck className="w-3.5 h-3.5 text-gold/70" /> Secure checkout by Paddle
            </div>
          )}
          {data.demo_reset_enabled && isPro && (
            <button onClick={resetDemo} data-testid="reset-demo-btn" className="w-full border border-white/10 text-zinc-500 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors mt-2">
              Revert activation (demo)
            </button>
          )}
        </div>
      </GlassCard>

      <p className="text-center text-[11px] text-zinc-600 mt-8 leading-relaxed">
        Payments processed by Paddle (Merchant of Record). Subscriptions renew automatically each billing period until you cancel
        in the Paddle customer portal. Cancel anytime.{" "}
        <Link to="/terms" className="text-zinc-500 hover:text-zinc-300 transition-colors">Terms</Link>
        {" · "}
        <Link to="/privacy" className="text-zinc-500 hover:text-zinc-300 transition-colors">Privacy</Link>
        {" · "}
        <Link to="/refunds" className="text-zinc-500 hover:text-zinc-300 transition-colors">Refunds</Link>
      </p>
    </div>
  );
}
