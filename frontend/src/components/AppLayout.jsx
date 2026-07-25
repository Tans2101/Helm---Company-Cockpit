import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, GitBranch, Activity, DollarSign, KanbanSquare,
  FileText, Users2, Calendar, Contact, MessageSquareText, Plug,
  LogOut, Sparkles, Menu, X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useFetch } from "@/hooks/useFetch";
import { ProBadge } from "@/components/kit";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Briefing", icon: LayoutDashboard, id: "briefing", end: true },
  { to: "/decisions", label: "Decisions", icon: GitBranch, id: "decisions" },
  { to: "/telemetry", label: "Telemetry", icon: Activity, id: "telemetry" },
  { to: "/financials", label: "Financials", icon: DollarSign, id: "financials" },
  { to: "/tasks", label: "Tasks", icon: KanbanSquare, id: "tasks" },
  { to: "/reports", label: "Reports", icon: FileText, id: "reports" },
  { to: "/team", label: "Team Bandwidth", icon: Users2, id: "team" },
  { to: "/calendar", label: "Calendar", icon: Calendar, id: "calendar" },
  { to: "/people", label: "People", icon: Contact, id: "people" },
  { to: "/ask", label: "Ask Kalun", icon: MessageSquareText, id: "ask" },
  { to: "/integrations", label: "Integrations", icon: Plug, id: "integrations" },
];

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
            <span className="font-mono text-gold text-sm font-medium">K</span>
          </div>
          <div>
            <p className="text-white text-[15px] font-semibold leading-none tracking-tight">Kalun</p>
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mt-1">CEO Operating System</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {NAV.map((item) => (
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
        {!isPro && (
          <button
            data-testid="sidebar-upgrade-btn"
            onClick={() => { navigate("/billing"); onNavigate?.(); }}
            className="w-full mb-3 rounded-lg border border-gold/25 bg-gradient-to-b from-gold/[0.12] to-transparent p-3 text-left transition-colors hover:border-gold/50"
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Sparkles className="w-3.5 h-3.5 text-gold" />
              <span className="text-xs font-medium text-white">Upgrade to Pro</span>
            </div>
            <p className="text-[11px] text-zinc-500 leading-snug">Live integrations, briefing & Weekly CEO Pack</p>
          </button>
        )}
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
            <p className="text-[10px] text-zinc-600 truncate">{isPro ? "Pro plan" : "Free plan"}</p>
          </div>
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

  return (
    <div className="min-h-screen grain">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[260px] flex-col bg-[#09090b] border-r border-white/5 z-40">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden sticky top-0 z-50 flex items-center justify-between px-4 h-14 bg-[#09090b]/90 backdrop-blur-md border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
            <span className="font-mono text-gold text-xs">K</span>
          </div>
          <span className="text-white font-semibold text-sm">Kalun</span>
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
          <Outlet />
        </div>
      </main>
    </div>
  );
}
