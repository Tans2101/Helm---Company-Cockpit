import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Sparkles, ArrowRight, ShieldCheck } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { initPaddle } from "@/lib/paddle";
import { PRO_FEATURES, PRO_PRICE, TAGLINE } from "@/lib/marketingCopy";

/**
 * Blocks cockpit usage until workspace has an active Pro subscription.
 * Billing route is always accessible (no overlay).
 */
export default function SubscriptionGate({ children, isPro, canManageBilling }) {
  const navigate = useNavigate();
  const { data: billing } = useFetch("/billing/plans");
  const [busy, setBusy] = useState(false);

  if (isPro) return children;

  const proPrice = billing?.pro_price ?? billing?.price ?? PRO_PRICE;
  const paddleReady = billing?.paddle_ready;

  const checkout = async () => {
    if (!paddleReady) {
      toast.error("Checkout is not configured yet — contact support.");
      return;
    }
    setBusy(true);
    try {
      const { data: cfg } = await api.post("/billing/paddle/config");
      const Paddle = await initPaddle(cfg.client_token, cfg.environment, (ev) => {
        if (ev?.name === "checkout.completed") {
          toast.success("Welcome to Helm Pro — activating…");
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
      toast.error(e?.response?.data?.detail || "Could not start checkout");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex-1 min-h-0">
      <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden>
        <div className="h-full blur-[6px] opacity-40 scale-[1.02]">{children}</div>
      </div>
      <div className="absolute inset-0 bg-[#09090b]/75 backdrop-blur-[2px] flex items-center justify-center p-6 z-20">
        <div className="w-full max-w-md rounded-2xl border border-gold/25 bg-[#121214]/95 p-8 text-center shadow-[0_0_60px_-15px_rgba(201,169,98,0.3)]">
          <Sparkles className="w-8 h-8 text-gold mx-auto" />
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold mt-4">Activation required</p>
          <h2 className="mt-3 text-2xl font-light tracking-tight text-white">Your cockpit is ready</h2>
          <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
            {TAGLINE} Activate Helm Pro to use the full CEO Operating System.
          </p>
          <p className="mt-4 font-mono text-3xl text-white">${proPrice}<span className="text-sm text-zinc-600">/mo</span></p>
          <ul className="mt-5 text-left space-y-2">
            {PRO_FEATURES.slice(0, 4).map((f) => (
              <li key={f} className="text-xs text-zinc-500 flex items-start gap-2">
                <span className="text-gold mt-0.5">✓</span> {f}
              </li>
            ))}
          </ul>
          {canManageBilling ? (
            <button type="button" onClick={checkout} disabled={busy || !paddleReady} data-testid="activate-pro-btn"
              className="mt-8 w-full rounded-full bg-gold text-black font-medium py-3 hover:bg-gold-hover transition-colors disabled:opacity-60">
              {busy ? "Starting checkout…" : `Activate Helm Pro — $${proPrice}/mo`}
            </button>
          ) : (
            <p className="mt-8 text-sm text-zinc-500">Ask your workspace owner to activate Helm Pro.</p>
          )}
          <div className="mt-4 flex flex-col gap-2 text-xs text-zinc-600">
            <Link to="/features" className="text-zinc-500 hover:text-white transition-colors">See what's included</Link>
            {canManageBilling && (
              <button type="button" onClick={() => navigate("/app/billing")} className="text-zinc-500 hover:text-white transition-colors">
                Billing details
              </button>
            )}
            {paddleReady && canManageBilling && (
              <span className="inline-flex items-center justify-center gap-1.5 mt-1">
                <ShieldCheck className="w-3.5 h-3.5 text-gold/70" /> Secure checkout by Paddle
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
