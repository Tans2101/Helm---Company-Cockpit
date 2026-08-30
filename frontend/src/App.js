import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { useClerk } from "@clerk/clerk-react";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import AuthCallback from "@/components/AuthCallback";
import ClerkHelmBridge from "@/components/ClerkHelmBridge";
import ClerkProviderBootstrap from "@/components/ClerkProviderBootstrap";
import ProtectedRoute from "@/components/ProtectedRoute";
import ProtectedRouteClerk from "@/components/ProtectedRouteClerk";
import ErrorBoundary from "@/components/ErrorBoundary";
import CookieNotice from "@/components/CookieNotice";
import Login from "@/pages/Login";
import SignUpPage from "@/pages/SignUp";
import Landing from "@/pages/Landing";
import Privacy from "@/pages/Privacy";
import Terms from "@/pages/Terms";
import Briefing from "@/pages/Briefing";
import MyDay from "@/pages/MyDay";
import Pipeline from "@/pages/Pipeline";
import Decisions from "@/pages/Decisions";
import Telemetry from "@/pages/Telemetry";
import Financials from "@/pages/Financials";
import Tasks from "@/pages/Tasks";
import Reports from "@/pages/Reports";
import Team from "@/pages/Team";
import CalendarPage from "@/pages/CalendarPage";
import People from "@/pages/People";
import AskHelm from "@/pages/AskHelm";
import Members from "@/pages/Members";
import Integrations from "@/pages/Integrations";
import Billing from "@/pages/Billing";
import PaymentSuccess from "@/pages/PaymentSuccess";
import PaymentCancel from "@/pages/PaymentCancel";
import AccountSettings from "@/pages/AccountSettings";

import { getClerkPublishableKey } from "@/lib/clerkConfig";

const HAS_CLERK = !!getClerkPublishableKey();

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login/*" element={<Login />} />
      <Route path="/sign-up/*" element={<SignUpPage />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/payment/success" element={<PaymentSuccess />} />
      <Route path="/payment/cancel" element={<PaymentCancel />} />
      <Route path="/app" element={HAS_CLERK ? <ProtectedRouteClerk /> : <ProtectedRoute />}>
        <Route index element={<Briefing />} />
        <Route path="me" element={<MyDay />} />
        <Route path="sales" element={<Pipeline />} />
        <Route path="decisions" element={<Decisions />} />
        <Route path="telemetry" element={<Telemetry />} />
        <Route path="financials" element={<Financials />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="reports" element={<Reports />} />
        <Route path="team" element={<Team />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="people" element={<People />} />
        <Route path="ask" element={<AskHelm />} />
        <Route path="members" element={<Members />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="billing" element={<Billing />} />
        <Route path="settings" element={<AccountSettings />} />
      </Route>
    </Routes>
  );
}

function ClerkAuthShell() {
  const { signOut } = useClerk();
  return (
    <AuthProvider onLogoutExtra={() => signOut()} deferInitialAuth>
      <ErrorBoundary>
        <BrowserRouter>
          <ClerkHelmBridge />
          <AppRouter />
          <CookieNotice />
          <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#141417", border: "1px solid rgba(255,255,255,0.08)", color: "#fff" } }} />
        </BrowserRouter>
      </ErrorBoundary>
    </AuthProvider>
  );
}

function HelmApp() {
  return (
    <AuthProvider>
      <ErrorBoundary>
        <BrowserRouter>
          <AppRouter />
          <CookieNotice />
          <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#141417", border: "1px solid rgba(255,255,255,0.08)", color: "#fff" } }} />
        </BrowserRouter>
      </ErrorBoundary>
    </AuthProvider>
  );
}

function App() {
  return (
    <div className="App">
      {HAS_CLERK ? (
        <ClerkProviderBootstrap>
          <ClerkAuthShell />
        </ClerkProviderBootstrap>
      ) : (
        <HelmApp />
      )}
    </div>
  );
}

export default App;
