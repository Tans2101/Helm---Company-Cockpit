import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, ArrowLeft, ShieldCheck, ExternalLink, AlertTriangle } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { initPaddle } from "@/lib/paddle";
import { PLANS } from "@/lib/marketingCopy";
import { normalizePlan } from "@/lib/helmPlan";
import { GlassCard, SectionLabel, LoadingScreen, ErrorScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

export default function Billing() {
  const { data, loading, error, reload } = useFetch("/billing/plans");
  const [busy, setBusy] = useState(null);
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
  const currentPlan = normalizePlan(data.current_plan);
  const plans = (data.plans?.length ? data.plans : PLANS).map((p) => ({
    ...p,
    includes: p.includes || PLANS.find((x) => x.id === p.id)?.includes || [],
    for: p.for || PLANS.find((x) => x.id === p.id)?.for,
    trial_days: p.trial_days ?? p.trialDays ?? 0,
  }));
  const pastDue = billingEnforced && data.subscription_status === "past_due";
  const trialing = data.subscription_status === "trialing";

  const activatePaddle = async (planId) => {
    if (planId === "free") return;
    const tier = plans.find((p) => p.id === planId);
    if (!tier?.checkout_available && data.paddle_ready === false) {
      toast.error("Paddle checkout is not configured yet");
      return;
    }
    if (tier && tier.checkout_available === false) {
      toast.error(`${tier.label} checkout isn’t set up yet — price ID coming soon`);
      return;
    }
    setBusy(planId);
    try {
      const { data: cfg } = await api.post("/billing/paddle/config", { plan: planId });
      const Paddle = await initPaddle(cfg.client_token, cfg.environment, (ev) => {
        if (ev?.name === "checkout.completed") {
          toast.success("Payment received — activating your plan…");
          setTimeout(() => window.location.reload(), 4500);
        }
      });
      Paddle.Checkout.open({
        settings: { displayMode: "overlay", theme: "dark" },
        items: [{ priceId: cfg.price_id, quantity: 1 }],
        customData: {
          workspace_id: cfg.workspace_id,
          user_id: cfg.user_id,
          checkout_nonce: cfg.checkout_nonce,
          plan: cfg.plan,
        },
        ...(cfg.email ? { customer: { email: cfg.email } } : {}),
      });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start Paddle checkout");
    } finally {
      setBusy(null);
    }
  };

  const openPortal = async () => {
    setBusy("portal");
    try {
      const { data: res } = await api.post("/payments/paddle/portal");
      if (res?.url) window.location.href = res.url;
      else toast.error("Could not open billing portal");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not open billing portal");
    } finally {
      setBusy(null);
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
    <div className="max-w-5xl mx-auto">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-white mb-6 transition-colors" data-testid="billing-back">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      {pastDue && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200" data-testid="past-due-banner">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-100">Payment past due</p>
            <p className="text-amber-200/80 mt-0.5">Update your payment method to keep paid features.</p>
            {data.portal_available && (
              <button onClick={openPortal} disabled={!!busy} className="mt-2 text-xs font-medium text-amber-100 underline hover:no-underline">
                Manage billing
              </button>
            )}
          </div>
        </div>
      )}

      {trialing && (
        <div className="mb-6 rounded-lg border border-gold/25 bg-gold/10 px-4 py-3 text-sm text-gold" data-testid="trialing-banner">
          You’re on a free trial — cancel anytime before it ends to avoid being charged.
        </div>
      )}

      {!billingEnforced && (
        <div className="mb-6 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200" data-testid="billing-standby-banner">
          <p className="font-medium text-emerald-100">Billing is paused</p>
          <p className="text-emerald-200/80 mt-0.5">
            Feature gates are open while you build. Set <code className="font-mono text-xs">BILLING_ENFORCED=true</code> when ready to charge.
            Configure <code className="font-mono text-xs">PADDLE_PRICE_ID_STARTER</code> / <code className="font-mono text-xs">_GROWTH</code> / <code className="font-mono text-xs">_BUSINESS</code> for checkout.
          </p>
        </div>
      )}

      <div className="text-center mb-10 fade-up">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-3">Pricing</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">Choose your Helm plan</h1>
        <p className="text-zinc-500 mt-3">
          Paid plans include a <span className="text-zinc-300">7-day free trial</span>. Cancel anytime.
        </p>
        {typeof data.seats_used === "number" && (
          <p className="text-xs text-zinc-600 mt-2 font-mono">
            Seats {data.seats_used}/{data.seats_limit == null ? "∞" : data.seats_limit}
            {data.ai_extracts_limit > 0 && (
              <> · AI extracts {data.ai_extracts_used}/{data.ai_extracts_limit} this month</>
            )}
          </p>
        )}
      </div>

      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {plans.map((plan) => {
          const isCurrent = currentPlan === plan.id;
          const isPaid = plan.id !== "free";
          const price = plan.price ?? 0;
          const highlighted = plan.id === "starter" || plan.highlighted;
          return (
            <GlassCard
              key={plan.id}
              glow={highlighted && !isCurrent}
              className={cn(
                "p-5 fade-up flex flex-col",
                isCurrent && "border-gold/40",
                highlighted && !isCurrent && "border-gold/25",
              )}
              data-testid={`plan-card-${plan.id}`}
            >
              <div className="flex items-center justify-between gap-2">
                <SectionLabel>{plan.label}</SectionLabel>
                {isCurrent && (
                  <span className="text-[10px] font-mono uppercase tracking-wide text-gold bg-gold/10 border border-gold/30 rounded px-1.5 py-0.5">
                    Current
                  </span>
                )}
              </div>
              <p className="font-mono text-3xl text-white mt-3">
                {price === 0 ? "$0" : `$${price}`}
                <span className="text-sm text-zinc-600">{price === 0 ? "" : "/mo"}</span>
              </p>
              <p className="text-xs text-zinc-500 mt-1 min-h-[2.5rem]">{plan.for}</p>
              {isPaid && (plan.trial_days || 7) > 0 && (
                <p className="text-[11px] text-gold/80 font-mono mt-1">{plan.trial_days || 7}-day free trial</p>
              )}
              <ul className="mt-4 space-y-2 flex-1">
                {(plan.includes || []).map((f) => (
                  <li key={f} className="flex items-start gap-2 text-xs text-zinc-300">
                    <Check className="w-3.5 h-3.5 text-gold shrink-0 mt-0.5" /> {f}
                  </li>
                ))}
              </ul>
              <div className="mt-5">
                {isCurrent ? (
                  <div className="text-center text-xs font-mono uppercase tracking-wide text-gold border border-gold/30 bg-gold/10 rounded-md py-2.5">
                    {isPaid ? "Active" : "On Free"}
                  </div>
                ) : isPaid ? (
                  <button
                    type="button"
                    data-testid={`upgrade-${plan.id}`}
                    onClick={() => activatePaddle(plan.id)}
                    disabled={!!busy || plan.checkout_available === false}
                    className="w-full bg-gold text-black font-medium rounded-md py-2.5 text-sm transition-colors hover:bg-gold-hover disabled:opacity-60"
                  >
                    {busy === plan.id
                      ? "Starting…"
                      : plan.checkout_available === false
                        ? "Coming soon"
                        : `Start ${plan.trial_days || 7}-day trial`}
                  </button>
                ) : (
                  <p className="text-center text-xs text-zinc-600 py-2">Included when you sign up</p>
                )}
              </div>
            </GlassCard>
          );
        })}
      </div>

      {data.portal_available && currentPlan !== "free" && (
        <button
          data-testid="manage-billing-btn"
          onClick={openPortal}
          disabled={!!busy}
          className="w-full max-w-md mx-auto flex items-center justify-center gap-2 border border-white/10 text-zinc-300 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors disabled:opacity-60 mb-4"
        >
          <ExternalLink className="w-4 h-4" /> Manage billing
        </button>
      )}

      {data.demo_reset_enabled && currentPlan !== "free" && (
        <button onClick={resetDemo} data-testid="reset-demo-btn" className="w-full max-w-md mx-auto block border border-white/10 text-zinc-500 rounded-md py-2.5 text-sm hover:bg-white/5 transition-colors mb-4">
          Revert to Free (demo)
        </button>
      )}

      <p className="text-center text-[11px] text-zinc-600 mt-6 leading-relaxed max-w-xl mx-auto">
        Payments processed by Paddle (Merchant of Record). Paid plans renew after the trial unless you cancel.
        Cancel anytime — access continues until the end of the billing period. No refunds after payment.{" "}
        <Link to="/terms" className="text-zinc-500 hover:text-zinc-300 transition-colors">Terms</Link>
        {" · "}
        <Link to="/privacy" className="text-zinc-500 hover:text-zinc-300 transition-colors">Privacy</Link>
        {" · "}
        <Link to="/refunds" className="text-zinc-500 hover:text-zinc-300 transition-colors">Refunds</Link>
      </p>
      <div className="flex items-center justify-center gap-1.5 text-[11px] text-zinc-600 mt-3">
        <ShieldCheck className="w-3.5 h-3.5 text-gold/70" /> Secure checkout by Paddle
      </div>
    </div>
  );
}
