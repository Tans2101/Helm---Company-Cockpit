import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, XCircle, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/kit";

export default function PaymentSuccess() {
  const [status, setStatus] = useState("checking"); // checking | paid | failed | timeout
  const navigate = useNavigate();
  const attempts = useRef(0);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    if (!sessionId) { setStatus("failed"); return; }

    let mounted = true;
    let timer;
    const poll = async () => {
      if (!mounted) return;
      if (attempts.current >= 8) { if (mounted) setStatus("timeout"); return; }
      attempts.current += 1;
      try {
        const { data } = await api.get(`/payments/status/${sessionId}`);
        if (!mounted) return;
        if (data.payment_status === "paid") { setStatus("paid"); return; }
        if (data.status === "expired" || data.payment_status === "failed") { setStatus("failed"); return; }
      } catch (e) { /* keep polling */ }
      if (mounted) timer = setTimeout(poll, 2000);
    };
    poll();
    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-helm-ink grain p-6">
      <div className="max-w-md w-full text-center relative z-10">
        {status === "checking" && (
          <>
            <Spinner className="w-8 h-8 mx-auto mb-6" />
            <h1 className="font-display text-2xl font-normal text-helm-fg">Confirming your payment…</h1>
            <p className="text-helm-muted text-sm mt-2">This only takes a moment.</p>
          </>
        )}
        {status === "paid" && (
          <>
            <div className="w-16 h-16 rounded-full bg-helm-gold/12 border border-helm-gold/35 flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="w-8 h-8 text-helm-gold" />
            </div>
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-helm-gold mb-3">Welcome to Helm</p>
            <h1 className="font-display text-3xl font-normal text-helm-fg">You're in command.</h1>
            <p className="text-helm-muted mt-3">Live integrations, AI briefings and the CEO Pack are now unlocked.</p>
            <button data-testid="success-continue-btn" onClick={() => navigate("/app")}
              className="mt-8 inline-flex items-center gap-2 rounded-md bg-helm-gold text-helm-navy font-medium px-5 py-2.5 text-sm transition-colors hover:bg-helm-gold-hover">
              Enter the cockpit <ArrowRight className="w-4 h-4" />
            </button>
          </>
        )}
        {(status === "failed" || status === "timeout") && (
          <>
            <div className="w-16 h-16 rounded-full bg-helm-status-negative/12 border border-helm-status-negative/35 flex items-center justify-center mx-auto mb-6">
              <XCircle className="w-8 h-8 text-helm-status-negative" />
            </div>
            <h1 className="font-display text-2xl font-normal text-helm-fg">{status === "timeout" ? "Still processing" : "Payment not completed"}</h1>
            <p className="text-helm-muted text-sm mt-2">
              {status === "timeout" ? "Your payment is taking longer than expected. Check billing shortly." : "No charge was made. You can try again anytime."}
            </p>
            <button onClick={() => navigate("/app/billing")} className="mt-8 rounded-md border border-helm-line text-helm-fg px-5 py-2.5 text-sm hover:bg-helm-fg/5 transition-colors">Back to billing</button>
          </>
        )}
      </div>
    </div>
  );
}
