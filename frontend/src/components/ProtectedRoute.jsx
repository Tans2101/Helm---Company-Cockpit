import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import AppLayout from "@/components/AppLayout";
import WorkspaceGate from "@/pages/WorkspaceGate";
import Onboarding from "@/pages/Onboarding";
import { hasPerm } from "@/lib/access";

function WaitingForSetup() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] grain p-6">
      <div className="relative z-10 max-w-md text-center">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold mb-4">Helm</p>
        <h1 className="text-2xl font-light text-white tracking-tight">Workspace setup in progress</h1>
        <p className="text-sm text-zinc-500 mt-3 leading-relaxed">
          Your owner still needs to finish onboarding. Refresh after they pick a template.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-8 rounded-md border border-white/10 text-white text-sm px-4 py-2 hover:bg-white/5 transition-colors"
          data-testid="onboarding-wait-refresh"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}

export default function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b]">
        <div className="w-7 h-7 rounded-full border-2 border-gold/30 border-t-gold animate-spin mb-5" />
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">Helm</p>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.needs_workspace) return <WorkspaceGate />;
  if (user.onboarding_done === false) {
    if (hasPerm(user, "workspace:edit")) {
      return (
        <div className="min-h-screen bg-[#09090b] grain">
          <div className="relative z-10 max-w-5xl mx-auto px-4 py-10">
            <Onboarding />
          </div>
        </div>
      );
    }
    return <WaitingForSetup />;
  }
  return <AppLayout />;
}
