import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function PaymentCancel() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center bg-helm-ink grain p-6">
      <div className="max-w-md w-full text-center relative z-10">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-helm-muted mb-3">Checkout cancelled</p>
        <h1 className="font-display text-3xl font-normal text-helm-fg">No worries. Nothing was charged.</h1>
        <p className="text-helm-muted mt-3">You can activate Helm whenever you're ready.</p>
        <button data-testid="cancel-back-btn" onClick={() => navigate("/app/billing")}
          className="mt-8 inline-flex items-center gap-2 rounded-md bg-helm-gold text-helm-navy font-medium px-5 py-2.5 text-sm transition-colors hover:bg-helm-gold-hover">
          <ArrowLeft className="w-4 h-4" /> Back to billing
        </button>
      </div>
    </div>
  );
}
