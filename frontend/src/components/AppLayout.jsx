import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, GitBranch, Activity, KanbanSquare,
  FileText, Calendar, Contact, MessageSquareText, Plug,
  LogOut, Menu, X, UsersRound, ChevronDown, Check, Plus, Sun,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { toast } from "sonner";
import SubscriptionGate from "@/components/SubscriptionGate";
import CompanySetup from "@/pages/CompanySetup";
import { helmPlanLabel, helmWorkspacePlanLabel, helmHasFullAccess } from "@/lib/helmPlan";
import { departmentIcon } from "@/lib/departmentIcons";
import { cn } from "@/lib/utils";
import { LoadingScreen } from "@/components/kit";
import { consumeReferralCode, withReferralPayload } from "@/lib/referral";
import { departmentPath } from "@/lib/departmentRoutes";

const NAV = [
  { to: "/app/me", label: "My Day", icon: Sun, id: "myday", end: true },
  { to: "/app", label: "Briefing", icon: LayoutDashboard, id: "briefing", end: true },
  { to: "/app/decisions", label: "Decisions", icon: GitBranch, id: "decisions" },
  { to: "/app/telemetry", label: "Telemetry", icon: Activity, id: "telemetry" },
  { to: "/app/tasks", label: "Tasks", icon: KanbanSquare, id: "tasks" },
  { to: "/app/reports", label: "Reports", icon: FileText, id: "reports" },
  { to: "/app/calendar", label: "Calendar", icon: Calendar, id: "calendar" },
  { to: "/app/people", label: "People", icon: Contact, id: "people" },
  { to: "/app/ask", label: "Ask Helm", icon: MessageSquareText, id: "ask" },
  { to: "/app/members", label: "Team & Access", icon: UsersRound, id: "members", perm: "members:invite" },
  { to: "/app/integrations", label: "Integrations", icon: Plug, id: "integrations" },
];

function departmentNavTo(type) {
  return departmentPath(type);
}

function WorkspaceSwitcher({ onNavigate, billingEnforced }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, reload } = useFetch("/workspaces");
  const [open, setOpen] = useState(false);
  const list = data?.workspaces || [];
  const active = list.find((w) => w.active) || list[0];

  const switchWs = async (id) => {
    if (id === active?.workspace_id) { setOpen(false); return; }
    try {
      await api.post("/workspaces/switch", { workspace_id: id });
      window.location.href = "/app";
    } catch (e) { toast.error("Could not switch workspace"); }
  };

  const create = async () => {
    const name = window.prompt("Name your new company workspace");
    if (!name) return;
    try {
      if (!user?.age_confirmed) {
        const ok = window.confirm(
          "Confirm you are 18 or older (or using Helm under a parent/guardian) to create a company.",
        );
        if (!ok) return;
        await api.patch("/account/age-confirmation", { confirmed: true });
      }
      await api.post("/workspaces", withReferralPayload({ name }));
      consumeReferralCode();
      window.location.href = "/app";
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not create workspace"); }
  };

  if (!active) return null;
  return (
    <div className="px-3 pt-3 relative">
      <button data-testid="workspace-switcher" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 rounded-md border border-helm-line bg-helm-card px-3 py-2 transition-colors hover:border-helm-gold/35">
        <div className="w-6 h-6 rounded bg-helm-gold/12 border border-helm-gold/35 flex items-center justify-center text-[11px] text-helm-gold font-mono shrink-0">
          {active.name?.[0]?.toUpperCase() || "K"}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="text-xs text-helm-fg truncate">{active.name}</p>
          <p className="text-[10px] text-helm-muted uppercase font-mono tracking-wide">{active.role} · {helmWorkspacePlanLabel(active.plan, billingEnforced)}</p>
        </div>
        <ChevronDown className={cn("w-4 h-4 text-helm-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute left-3 right-3 mt-1 z-50 rounded-md border border-helm-line bg-helm-card shadow-xl overflow-hidden">
          {list.map((w) => (
            <button key={w.workspace_id} onClick={() => switchWs(w.workspace_id)}
              data-testid={`ws-option-${w.workspace_id}`}
              className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-helm-fg/5">
              <span className="flex-1 min-w-0 text-xs text-helm-fg truncate">{w.name}</span>
              {w.active && <Check className="w-3.5 h-3.5 text-helm-gold" />}
            </button>
          ))}
          <button onClick={create} data-testid="ws-create-btn"
            className="w-full flex items-center gap-2 px-3 py-2 text-left border-t border-helm-line transition-colors hover:bg-helm-fg/5 text-helm-gold">
            <Plus className="w-3.5 h-3.5" /><span className="text-xs">New company</span>
          </button>
        </div>
      )}
    </div>
  );
}

function SidebarContent({ onNavigate, billingEnforced }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: company } = useFetch("/company");
  const { data: deptData } = useFetch("/departments");
  const isPro = helmHasFullAccess(company?.plan, billingEnforced);
  const deptNav = (deptData?.departments || []).filter((d) => d.visible_in_nav);

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-6 border-b border-helm-line">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-helm-gold/12 border border-helm-gold/35 flex items-center justify-center">
            <span className="font-mono text-helm-gold text-sm font-medium">H</span>
          </div>
          <div>
            <p className="text-helm-fg text-[15px] font-semibold leading-none tracking-tight">Helm</p>
            <p className="text-[10px] uppercase tracking-[0.14em] text-helm-muted mt-1">Company cockpit</p>
          </div>
        </div>
      </div>

      <WorkspaceSwitcher onNavigate={onNavigate} billingEnforced={billingEnforced} />

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {NAV.filter((item) => !item.perm || (user?.perms || []).includes(item.perm)).map((item) => (
          <NavLink
            key={item.id}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            data-testid={`sidebar-nav-${item.id}`}
            className={({ isActive }) =>
              cn(
                "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-200",
                isActive
                  ? "bg-helm-gold/12 text-helm-fg"
                  : "text-helm-muted hover:text-helm-fg hover:bg-helm-fg/[0.03]"
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[2px] rounded-full bg-helm-gold" />}
                <item.icon className={cn("w-[18px] h-[18px] shrink-0", isActive ? "text-helm-gold" : "text-helm-muted group-hover:text-helm-fg")} />
                <span className="truncate">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}

        {deptNav.length > 0 && (
          <div className="pt-3 mt-2 border-t border-helm-line">
            <p className="px-3 mb-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-helm-muted">Departments</p>
            {deptNav.map((dept) => {
              const Icon = departmentIcon(dept.icon);
              const to = departmentNavTo(dept.type);
              return (
                <NavLink
                  key={dept.type}
                  to={to}
                  onClick={onNavigate}
                  data-testid={`sidebar-dept-${dept.type}`}
                  className={({ isActive }) =>
                    cn(
                      "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-200",
                      isActive
                        ? "bg-helm-gold/12 text-helm-fg"
                        : "text-helm-muted hover:text-helm-fg hover:bg-helm-fg/[0.03]"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[2px] rounded-full bg-helm-gold" />}
                      <Icon className={cn("w-[18px] h-[18px] shrink-0", isActive ? "text-helm-gold" : "text-helm-muted group-hover:text-helm-fg")} />
                      <span className="truncate">{dept.name}</span>
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        )}
      </nav>

      <div className="px-3 pb-4">
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          {user?.picture ? (
            <img src={user.picture} alt="" className="w-8 h-8 rounded-full object-cover border border-helm-line" />
          ) : (
            <div className="w-8 h-8 rounded-full bg-helm-fg/10 flex items-center justify-center text-xs text-helm-fg">
              {user?.name?.[0] || "C"}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-helm-fg truncate">{user?.name || "CEO"}</p>
            {(user?.perms || []).includes("billing:manage") ? (
              <button
                type="button"
                data-testid="sidebar-billing-link"
                onClick={() => { navigate("/app/billing"); onNavigate?.(); }}
                className="text-[10px] text-helm-muted truncate hover:text-helm-gold transition-colors text-left"
              >
                {helmPlanLabel(company?.plan, isPro, billingEnforced)} · Billing
              </button>
            ) : (
              <p className="text-[10px] text-helm-muted truncate">{helmPlanLabel(company?.plan, isPro, billingEnforced)}</p>
            )}
          </div>
          <button
            data-testid="settings-link"
            onClick={() => { navigate("/app/settings"); onNavigate?.(); }}
            className="text-helm-muted hover:text-helm-fg transition-colors text-[10px] font-mono uppercase tracking-wide"
            title="Settings"
          >
            Settings
          </button>
          <button data-testid="logout-btn" onClick={logout} className="text-helm-muted hover:text-helm-fg transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { user } = useAuth();
  const { data: billing } = useFetch("/billing/plans");
  const { data: company, loading: companyLoading } = useFetch("/company");
  const billingEnforced = billing?.billing_enforced === true;
  const pastDue = billingEnforced && billing?.subscription_status === "past_due";
  const isPro = helmHasFullAccess(company?.plan, billingEnforced);
  const onBilling = location.pathname.startsWith("/app/billing");
  const canManageBilling = user?.role === "owner" || (user?.perms || []).includes("billing:manage");
  const needsCompanySetup = company?.role === "owner" && company?.company_setup_done === false;

  if (companyLoading && !company) {
    return <LoadingScreen label="Loading Helm" />;
  }

  if (needsCompanySetup) {
    return <CompanySetup company={company} />;
  }

  return (
    <div className="app-shell min-h-screen">
      {pastDue && (
        <div className="lg:pl-[260px] bg-helm-status-warning/12 border-b border-helm-status-warning/35 px-5 py-2.5 text-center text-sm text-helm-fg" data-testid="global-past-due-banner">
          Payment past due — <button type="button" onClick={() => window.location.href = "/app/billing"} className="underline font-medium text-helm-status-warning">update billing</button> to keep Helm access.
        </div>
      )}
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[260px] flex-col bg-helm-bg border-r border-helm-line z-40">
        <SidebarContent billingEnforced={billingEnforced} />
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden sticky top-0 z-50 flex items-center justify-between px-4 h-14 bg-helm-bg/95 backdrop-blur-md border-b border-helm-line">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-helm-gold/12 border border-helm-gold/35 flex items-center justify-center">
            <span className="font-mono text-helm-gold text-xs">H</span>
          </div>
          <span className="text-helm-fg font-semibold text-sm">Helm</span>
        </div>
        <button data-testid="mobile-menu-btn" onClick={() => setMobileOpen(true)} className="text-helm-fg">
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-helm-ink/70" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-helm-bg border-r border-helm-line">
            <button onClick={() => setMobileOpen(false)} className="absolute top-4 right-4 text-helm-muted z-10">
              <X className="w-5 h-5" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} billingEnforced={billingEnforced} />
          </div>
        </div>
      )}

      <main className="lg:pl-[260px] relative z-10">
        <div className="px-5 md:px-10 py-8 md:py-12 max-w-[1500px]">
          {onBilling ? (
            <Outlet />
          ) : (
            <SubscriptionGate isPro={isPro} canManageBilling={canManageBilling}>
              <Outlet />
            </SubscriptionGate>
          )}
        </div>
      </main>
    </div>
  );
}
