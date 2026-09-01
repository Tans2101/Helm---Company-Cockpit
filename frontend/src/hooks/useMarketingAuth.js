import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useClerkMode } from "@/components/ClerkProviderBootstrap";

/** Auth state + enter handler for public marketing pages. */
export function useMarketingAuth() {
  const { user, loading } = useAuth();
  const { configLoading } = useClerkMode();
  const navigate = useNavigate();

  const authed = !loading && !!user;
  const enter = () => navigate(authed ? "/app" : "/sign-up");
  return { authed, enter, loading: loading || configLoading };
}
