import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { initPaddle } from "@/lib/paddle";
import { HELM_FEATURES, HELM_PRICE, TAGLINE } from "@/lib/marketingCopy";
import HelmHowToUse from "@/components/HelmHowToUse";

/**
 * Pre-activation shell: onboarding guide + subscription activation.
 * Billing route bypasses this gate in AppLayout.
 */
export default function SubscriptionGate({ children, isPro, canManageBilling }) {
  const navigate = useNavigate();
  const { data: billing } = useFetch("/billing/plans");
  const [busy, setBusy] = useState(false);

  if (isPro) return children;

  const helmPrice = billing?.pro_price ?? billing?.price ?? HELM_PRICE;
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
          toast.success("Welcome to Helm — activating…");
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
      {/* Blurred preview of the cockpit behind */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden>
        <div className="h-full blur-[5px] opacity-30 scale-[1.01]">{children}</div>
      </div>

      <div className="relative z-20 pb-16">
        <HelmHowToUse className="px-2 md:px-0" />

        {/* Activation */}
        <div
          id="activate-helm"
          className="mt-12 w-full max-w-3xl mx-auto rounded-2xl border border-gold/25 bg-[#121214]/95 p-8 md:p-10 shadow-[0_0_60px_-15px_rgba(201,169,98,0.25)]"
        >
          <div className="text-center md:text-left md:flex md:items-start md:justify-between md:gap-10">
            <div className="flex-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-gold">Activate Helm</p>
              <h3 className="mt-2 text-xl font-light tracking-tight text-white">
                Ready to run the business?
              </h3>
              <p className="mt-2 text-sm text-zinc-400 leading-relaxed max-w-md">
                {TAGLINE} Activate Helm to unlock the full cockpit — briefing, decisions, AI, and integrations.
              </p>
              <ul className="mt-5 space-y-2 text-left">
                {HELM_FEATURES.slice(0, 4).map((f) => (
                  <li key={f} className="text-xs text-zinc-500 flex items-start gap-2">
                    <span className="text-gold mt-0.5">✓</span> {f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="mt-8 md:mt-0 md:w-56 shrink-0 text-center md:text-right">
              <p className="font-mono text-4xl text-white">
                ${helmPrice}
                <span className="text-sm text-zinc-600">/mo</span>
              </p>
              <p className="text-[10px] font-mono uppercase tracking-wider text-zinc-600 mt-1">One plan · full cockpit</p>
              {canManageBilling ? (
                <button
                  type="button"
                  onClick={checkout}
                  disabled={busy || !paddleReady}
                  data-testid="activate-helm-btn"
                  className="mt-5 w-full rounded-full bg-gold text-black font-medium py-3 hover:bg-gold-hover transition-colors disabled:opacity-60"
                >
                  {busy ? "Starting checkout…" : `Activate Helm — $${helmPrice}/mo`}
                </button>
              ) : (
                <p className="mt-5 text-sm text-zinc-500">Ask your workspace owner to activate Helm.</p>
              )}
              <div className="mt-4 flex flex-col gap-2 text-xs text-zinc-600">
                <button
                  type="button"
                  onClick={() => navigate("/app/billing")}
                  className="text-zinc-500 hover:text-white transition-colors"
                >
                  Billing details
                </button>
                {paddleReady && canManageBilling && (
                  <span className="inline-flex items-center justify-center md:justify-end gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-gold/70" /> Secure checkout by Paddle
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
