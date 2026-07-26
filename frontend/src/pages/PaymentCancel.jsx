import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function PaymentCancel() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#09090b] grain p-6">
      <div className="max-w-md w-full text-center relative z-10">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-600 mb-3">Checkout cancelled</p>
        <h1 className="text-3xl font-light text-white">No worries — nothing was charged.</h1>
        <p className="text-zinc-500 mt-3">You can upgrade to Pro whenever you're ready.</p>
        <button data-testid="cancel-back-btn" onClick={() => navigate("/app/billing")}
          className="mt-8 inline-flex items-center gap-2 rounded-md bg-gold text-black font-medium px-5 py-2.5 text-sm transition-colors hover:bg-gold-hover">
          <ArrowLeft className="w-4 h-4" /> Back to billing
        </button>
      </div>
    </div>
  );
}
