import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import AuthCallback from "@/components/AuthCallback";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import Landing from "@/pages/Landing";
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
import AskKalun from "@/pages/AskKalun";
import Members from "@/pages/Members";
import Integrations from "@/pages/Integrations";
import Billing from "@/pages/Billing";
import PaymentSuccess from "@/pages/PaymentSuccess";
import PaymentCancel from "@/pages/PaymentCancel";

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/payment/success" element={<PaymentSuccess />} />
      <Route path="/payment/cancel" element={<PaymentCancel />} />
      <Route path="/app" element={<ProtectedRoute />}>
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
        <Route path="ask" element={<AskKalun />} />
        <Route path="members" element={<Members />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="billing" element={<Billing />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
      </AuthProvider>
      <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#141417", border: "1px solid rgba(255,255,255,0.08)", color: "#fff" } }} />
    </div>
  );
}

export default App;
