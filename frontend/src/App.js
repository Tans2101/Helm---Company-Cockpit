import "@/App.css";
import { lazy, Suspense, useEffect } from "react";
import { Analytics } from "@vercel/analytics/react";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { useClerk, AuthenticateWithRedirectCallback } from "@clerk/clerk-react";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import ClerkHelmBridge from "@/components/ClerkHelmBridge";
import AppearanceSync from "@/components/AppearanceSync";
import ClerkProviderBootstrap, { useClerkMode } from "@/components/ClerkProviderBootstrap";
import ProtectedRoute from "@/components/ProtectedRoute";
import ProtectedRouteClerk from "@/components/ProtectedRouteClerk";
import { clerkAfterAuthRedirect } from "@/lib/clerkRedirect";
import { persistReferralFromSearch } from "@/lib/referral";
import ErrorBoundary from "@/components/ErrorBoundary";
import CookieNotice from "@/components/CookieNotice";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import SignUpPage from "@/pages/SignUp";
import { LoadingScreen } from "@/components/kit";
import { useTheme } from "@/context/ThemeContext";
import palette from "@/design/palette.json";

const About = lazy(() => import("@/pages/About"));
const Features = lazy(() => import("@/pages/Features"));
const Security = lazy(() => import("@/pages/Security"));
const Privacy = lazy(() => import("@/pages/Privacy"));
const Terms = lazy(() => import("@/pages/Terms"));
const Refunds = lazy(() => import("@/pages/Refunds"));
const Briefing = lazy(() => import("@/pages/Briefing"));
const MyDay = lazy(() => import("@/pages/MyDay"));
const Pipeline = lazy(() => import("@/pages/Pipeline"));
const Decisions = lazy(() => import("@/pages/Decisions"));
const Telemetry = lazy(() => import("@/pages/Telemetry"));
const Financials = lazy(() => import("@/pages/Financials"));
const Tasks = lazy(() => import("@/pages/Tasks"));
const Reports = lazy(() => import("@/pages/Reports"));
const CalendarPage = lazy(() => import("@/pages/CalendarPage"));
const People = lazy(() => import("@/pages/People"));
const AskHelm = lazy(() => import("@/pages/AskHelm"));
const Members = lazy(() => import("@/pages/Members"));
const Integrations = lazy(() => import("@/pages/Integrations"));
const Billing = lazy(() => import("@/pages/Billing"));
const PaymentSuccess = lazy(() => import("@/pages/PaymentSuccess"));
const PaymentCancel = lazy(() => import("@/pages/PaymentCancel"));
const AccountSettings = lazy(() => import("@/pages/AccountSettings"));
const DepartmentPlaceholder = lazy(() => import("@/pages/DepartmentPlaceholder"));
const NotFound = lazy(() => import("@/pages/NotFound"));
const Production = lazy(() => import("@/pages/Production"));
const Procurement = lazy(() => import("@/pages/Procurement"));
const Legal = lazy(() => import("@/pages/Legal"));
const Maintenance = lazy(() => import("@/pages/Maintenance"));
const HR = lazy(() => import("@/pages/HR"));

function ClerkOAuthCallback() {
  const { postAuthUrl, clerkMultiDomain } = useClerkMode();
  const redirectUrl = clerkAfterAuthRedirect({ clerkMultiDomain, postAuthUrl });
  return (
    <AuthenticateWithRedirectCallback
      signInForceRedirectUrl={redirectUrl}
      signUpForceRedirectUrl={redirectUrl}
      signInFallbackRedirectUrl={redirectUrl}
      signUpFallbackRedirectUrl={redirectUrl}
    />
  );
}

function HelmToaster() {
  const { resolvedTheme } = useTheme();
  const light = resolvedTheme === "light";
  return (
    <Toaster
      theme={resolvedTheme}
      position="top-right"
      toastOptions={{
        style: {
          background: light ? palette.cream : palette.inkCard,
          border: `1px solid ${light ? palette.navy : palette.cream}29`,
          color: light ? palette.navy : palette.cream,
        },
      }}
    />
  );
}

function ClerkOAuthCallbackGuard() {
  const { clerkEnabled } = useClerkMode();
  if (!clerkEnabled) {
    return <Navigate to="/login" replace />;
  }
  return <ClerkOAuthCallback />;
}

function AppRouter() {
  const location = useLocation();
  useEffect(() => {
    persistReferralFromSearch(location.search);
  }, [location.search]);
  const { clerkEnabled, configLoading } = useClerkMode();
  const Protected = configLoading
    ? () => <LoadingScreen label="Loading cockpit" />
    : clerkEnabled
      ? ProtectedRouteClerk
      : ProtectedRoute;

  if (location.hash?.includes("session_id=")) {
    return <Navigate to="/login?error=session_retired" replace />;
  }
  return (
    <Suspense fallback={<LoadingScreen label="Loading" />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/about" element={<About />} />
        <Route path="/features" element={<Features />} />
        <Route path="/security" element={<Security />} />
        <Route path="/login/sso-callback" element={<ClerkOAuthCallbackGuard />} />
        <Route path="/sign-up/sso-callback" element={<ClerkOAuthCallbackGuard />} />
        <Route path="/login/*" element={<Login />} />
        <Route path="/sign-up/*" element={<SignUpPage />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/refunds" element={<Refunds />} />
        <Route path="/payment/success" element={<PaymentSuccess />} />
        <Route path="/payment/cancel" element={<PaymentCancel />} />
        <Route path="/app" element={<Protected />}>
          <Route index element={<Briefing />} />
          <Route path="me" element={<MyDay />} />
          <Route path="sales" element={<Pipeline />} />
          <Route path="decisions" element={<Decisions />} />
          <Route path="telemetry" element={<Telemetry />} />
          <Route path="financials" element={<Financials />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="reports" element={<Reports />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="people" element={<People />} />
          <Route path="ask" element={<AskHelm />} />
          <Route path="members" element={<Members />} />
          <Route path="integrations" element={<Integrations />} />
          <Route path="billing" element={<Billing />} />
          <Route path="settings" element={<AccountSettings />} />
          <Route path="departments/production" element={<Production />} />
          <Route path="departments/procurement" element={<Procurement />} />
          <Route path="departments/legal" element={<Legal />} />
          <Route path="departments/engineering_maintenance" element={<Maintenance />} />
          <Route path="departments/hr" element={<HR />} />
          <Route path="departments/sales" element={<Navigate to="/app/sales" replace />} />
          <Route path="departments/accounting_finance" element={<Navigate to="/app/financials" replace />} />
          <Route path="departments/:deptType" element={<DepartmentPlaceholder />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

function ClerkAuthShell() {
  const { signOut } = useClerk();
  return (
    <AuthProvider onLogoutExtra={() => signOut()} deferInitialAuth>
      <ErrorBoundary>
        <BrowserRouter>
          <AppearanceSync />
          <ClerkHelmBridge />
          <AppRouter />
          <CookieNotice />
          <HelmToaster />
        </BrowserRouter>
      </ErrorBoundary>
    </AuthProvider>
  );
}

function HelmAppShell() {
  return (
    <AuthProvider>
      <ErrorBoundary>
        <BrowserRouter>
          <AppearanceSync />
          <AppRouter />
          <CookieNotice />
          <HelmToaster />
        </BrowserRouter>
      </ErrorBoundary>
    </AuthProvider>
  );
}

function AuthShell() {
  const { clerkEnabled } = useClerkMode();
  return clerkEnabled ? <ClerkAuthShell /> : <HelmAppShell />;
}

function App() {
  return (
    <div className="App">
      <ClerkProviderBootstrap>
        <AuthShell />
      </ClerkProviderBootstrap>
      <Analytics />
    </div>
  );
}

export default App;
