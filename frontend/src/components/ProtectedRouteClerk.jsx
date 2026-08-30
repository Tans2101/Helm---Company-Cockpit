import { Navigate } from "react-router-dom";
import { useAuth as useClerkAuth } from "@clerk/clerk-react";
import { useAuth } from "@/context/AuthContext";
import AppLayout from "@/components/AppLayout";
import WorkspaceGate from "@/pages/WorkspaceGate";
import { LoadingScreen } from "@/components/kit";

/** Protected routes when Clerk is enabled — wait for Clerk→Helm session exchange. */
export default function ProtectedRouteClerk() {
  const { user, loading } = useAuth();
  const { isLoaded: clerkLoaded, isSignedIn } = useClerkAuth();

  if (loading || !clerkLoaded || (isSignedIn && !user)) {
    return <LoadingScreen label="Loading cockpit" />;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.needs_workspace) return <WorkspaceGate />;
  return <AppLayout />;
}
