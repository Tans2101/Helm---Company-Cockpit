import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, GitBranch, Activity, DollarSign, KanbanSquare,
  FileText, Users2, Calendar, Contact, MessageSquareText, Plug,
  LogOut, Menu, X, UsersRound, ChevronDown, Check, Plus, Sun, Briefcase,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { toast } from "sonner";
import SubscriptionGate from "@/components/SubscriptionGate";
import { helmPlanLabel, helmWorkspacePlanLabel } from "@/lib/helmPlan";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/app/me", label: "My Day", icon: Sun, id: "myday", end: true },
  { to: "/app", label: "Briefing", icon: LayoutDashboard, id: "briefing", end: true },
  { to: "/app/decisions", label: "Decisions", icon: GitBranch, id: "decisions" },
  { to: "/app/sales", label: "Pipeline", icon: Briefcase, id: "sales", perm: "sales:write" },
  { to: "/app/telemetry", label: "Telemetry", icon: Activity, id: "telemetry" },
  { to: "/app/financials", label: "Financials", icon: DollarSign, id: "financials" },
  { to: "/app/tasks", label: "Tasks", icon: KanbanSquare, id: "tasks" },
  { to: "/app/reports", label: "Reports", icon: FileText, id: "reports" },
  { to: "/app/team", label: "Team Bandwidth", icon: Users2, id: "team" },
  { to: "/app/calendar", label: "Calendar", icon: Calendar, id: "calendar" },
  { to: "/app/people", label: "People", icon: Contact, id: "people" },
  { to: "/app/ask", label: "Ask Helm", icon: MessageSquareText, id: "ask" },
  { to: "/app/members", label: "Team & Access", icon: UsersRound, id: "members", perm: "members:invite" },
  { to: "/app/integrations", label: "Integrations", icon: Plug, id: "integrations" },
];

function WorkspaceSwitcher({ onNavigate }) {
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
      await api.post("/workspaces", { name });
      window.location.href = "/app";
    } catch (e) { toast.error("Could not create workspace"); }
  };

  if (!active) return null;
  return (
    <div className="px-3 pt-3 relative">
      <button data-testid="workspace-switcher" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 rounded-md border border-white/5 bg-white/[0.02] px-3 py-2 transition-colors hover:border-white/10">
        <div className="w-6 h-6 rounded bg-gold/15 border border-gold/30 flex items-center justify-center text-[11px] text-gold font-mono shrink-0">
          {active.name?.[0]?.toUpperCase() || "K"}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="text-xs text-white truncate">{active.name}</p>
          <p className="text-[10px] text-zinc-600 uppercase font-mono tracking-wide">{active.role} · {helmWorkspacePlanLabel(active.plan)}</p>
        </div>
        <ChevronDown className={cn("w-4 h-4 text-zinc-500 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute left-3 right-3 mt-1 z-50 rounded-md border border-white/10 bg-[#141417] shadow-xl overflow-hidden">
          {list.map((w) => (
            <button key={w.workspace_id} onClick={() => switchWs(w.workspace_id)}
              data-testid={`ws-option-${w.workspace_id}`}
              className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-white/5">
              <span className="flex-1 min-w-0 text-xs text-white truncate">{w.name}</span>
              {w.active && <Check className="w-3.5 h-3.5 text-gold" />}
            </button>
          ))}
          <button onClick={create} data-testid="ws-create-btn"
            className="w-full flex items-center gap-2 px-3 py-2 text-left border-t border-white/5 transition-colors hover:bg-white/5 text-gold">
            <Plus className="w-3.5 h-3.5" /><span className="text-xs">New company</span>
          </button>
        </div>
      )}
    </div>
  );
}

function SidebarContent({ onNavigate }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { data: company } = useFetch("/company");
  const isPro = company?.plan === "pro";

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-6 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
            <span className="font-mono text-gold text-sm font-medium">H</span>
          </div>
          <div>
            <p className="text-white text-[15px] font-semibold leading-none tracking-tight">Helm</p>
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mt-1">CEO Operating System</p>
          </div>
        </div>
      </div>

      <WorkspaceSwitcher onNavigate={onNavigate} />

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
                  ? "bg-gold/[0.08] text-white"
                  : "text-zinc-400 hover:text-white hover:bg-white/[0.03]"
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[2px] rounded-full bg-gold" />}
                <item.icon className={cn("w-[18px] h-[18px] shrink-0", isActive ? "text-gold" : "text-zinc-500 group-hover:text-zinc-300")} />
                <span className="truncate">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 pb-4">
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          {user?.picture ? (
            <img src={user.picture} alt="" className="w-8 h-8 rounded-full object-cover border border-white/10" />
          ) : (
            <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs text-white">
              {user?.name?.[0] || "C"}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-white truncate">{user?.name || "CEO"}</p>
            <p className="text-[10px] text-zinc-600 truncate">{helmPlanLabel(company?.plan, isPro)}</p>
          </div>
          <button
            data-testid="settings-link"
            onClick={() => { navigate("/app/settings"); onNavigate?.(); }}
            className="text-zinc-500 hover:text-white transition-colors text-[10px] font-mono uppercase tracking-wide"
            title="Settings"
          >
            Settings
          </button>
          <button data-testid="logout-btn" onClick={logout} className="text-zinc-500 hover:text-white transition-colors">
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
  const { data: company } = useFetch("/company");
  const pastDue = billing?.subscription_status === "past_due";
  const isPro = company?.plan === "pro";
  const onBilling = location.pathname.startsWith("/app/billing");
  const canManageBilling = user?.role === "owner" || (user?.perms || []).includes("billing:manage");

  return (
    <div className="min-h-screen grain">
      {pastDue && (
        <div className="lg:pl-[260px] bg-amber-500/10 border-b border-amber-500/30 px-5 py-2.5 text-center text-sm text-amber-200" data-testid="global-past-due-banner">
          Payment past due — <button type="button" onClick={() => window.location.href = "/app/billing"} className="underline font-medium text-amber-100">update billing</button> to keep Helm access.
        </div>
      )}
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[260px] flex-col bg-[#09090b] border-r border-white/5 z-40">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden sticky top-0 z-50 flex items-center justify-between px-4 h-14 bg-[#09090b]/90 backdrop-blur-md border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
            <span className="font-mono text-gold text-xs">H</span>
          </div>
          <span className="text-white font-semibold text-sm">Helm</span>
        </div>
        <button data-testid="mobile-menu-btn" onClick={() => setMobileOpen(true)} className="text-white">
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/70" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-[#09090b] border-r border-white/10">
            <button onClick={() => setMobileOpen(false)} className="absolute top-4 right-4 text-zinc-400 z-10">
              <X className="w-5 h-5" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
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
