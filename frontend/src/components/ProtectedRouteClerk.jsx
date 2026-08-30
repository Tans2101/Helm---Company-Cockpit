import { Navigate } from "react-router-dom";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useAuth } from "@/context/AuthContext";
import AppLayout from "@/components/AppLayout";
import WorkspaceGate from "@/pages/WorkspaceGate";
import { LoadingScreen } from "@/components/kit";

/** Protected routes when Clerk is enabled — wait for Clerk→Helm session exchange. */
export default function ProtectedRouteClerk() {
  const { user, loading, sessionError } = useAuth();
  const { isLoaded: clerkLoaded, isSignedIn } = useClerkAuth();

  if (sessionError) {
    return <Navigate to="/login" replace />;
  }

  if (!clerkLoaded || loading) {
    return <LoadingScreen label="Loading cockpit" />;
  }

  if (user) {
    if (user.needs_workspace) return <WorkspaceGate />;
    return <AppLayout />;
  }

  if (isSignedIn) {
    return <LoadingScreen label="Connecting your account" />;
  }

  return <Navigate to="/login" replace />;
}
