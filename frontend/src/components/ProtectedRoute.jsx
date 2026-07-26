import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import AppLayout from "@/components/AppLayout";

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
  return <AppLayout />;
}
