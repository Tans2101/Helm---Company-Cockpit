import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Calendar, Mail, DollarSign, Github, MessageSquare, Cloud, Building2, Check,
  ExternalLink, KeyRound, RefreshCw, Sparkles, Upload, CreditCard, Clock, ArrowRight,
} from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen, ErrorScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const ICONS = {
  google_calendar: Calendar,
  gmail: Mail,
  quickbooks: Building2,
  helm_ai: Sparkles,
  document_storage: Upload,
  team_email: Mail,
  paddle: CreditCard,
  github: Github,
  slack: MessageSquare,
  salesforce: Cloud,
};

const STATUS_LABELS = {
  connected: { text: "Connected", className: "text-emerald-400 bg-emerald-400/10" },
  ready: { text: "Ready", className: "text-emerald-400 bg-emerald-400/10" },
  keys_needed: { text: "Keys needed", className: "text-amber-400 bg-amber-400/10" },
  not_connected: { text: "Not connected", className: "text-zinc-500 border border-white/10" },
  coming_soon: { text: "Coming soon", className: "text-zinc-500 border border-white/10" },
};

function formatLastSynced(iso) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function StatusBadge({ status }) {
  const cfg = STATUS_LABELS[status] || STATUS_LABELS.not_connected;
  const Icon = status === "connected" || status === "ready" ? Check : status === "keys_needed" ? KeyRound : null;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide rounded px-2 py-1", cfg.className)}>
      {Icon && <Icon className="w-3 h-3" />}
      {cfg.text}
    </span>
  );
}

function IntegrationCard({ it, canManage, onConnect, onDisconnect, onSync, onNavigate, qbSyncing }) {
  const Icon = ICONS[it.id] || Cloud;
  const status = it.status || (it.connected ? "connected" : it.configured === false ? "keys_needed" : "not_connected");
  const lastSynced = it.provider === "quickbooks" ? formatLastSynced(it.last_synced_at) : null;
  const isComingSoon = it.coming_soon || status === "coming_soon";
  const isOAuth = it.kind === "oauth" && it.oauth;
  const isPlatform = it.kind === "platform";
  const isBilling = it.kind === "billing";

  const primaryAction = () => {
    if (isComingSoon) return;
    if (isOAuth) {
      it.connected ? onDisconnect(it.provider) : onConnect(it.provider);
      return;
    }
    if (it.cta_route) onNavigate(it.cta_route);
  };

  const primaryLabel = () => {
    if (isComingSoon) return "Coming soon";
    if (isOAuth) {
      if (it.connected) return "Disconnect";
      if (status === "keys_needed") return "Set up on Render";
      return "Connect";
    }
    if (isPlatform) {
      if (status === "keys_needed") return "Set keys on Render";
      return it.cta_label || "Open";
    }
    if (isBilling) return it.cta_label || "Open billing";
    return it.connected ? "Disconnect" : "Connect";
  };

  return (
    <GlassCard key={it.id} className="p-5 fade-up flex flex-col" data-testid={`integration-${it.id}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
          <Icon className="w-5 h-5 text-gold" />
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <h3 className="text-white font-medium">{it.name}</h3>
        {isOAuth && <span className="text-[9px] font-mono uppercase tracking-wider text-gold/70 border border-gold/20 rounded px-1.5 py-0.5">OAuth</span>}
        {isPlatform && <span className="text-[9px] font-mono uppercase tracking-wider text-sky-400/80 border border-sky-400/20 rounded px-1.5 py-0.5">Platform</span>}
      </div>

      <p className="text-[11px] font-mono uppercase tracking-wide text-zinc-600 mt-0.5">{it.category}</p>
      <p className="text-sm text-zinc-500 mt-2 leading-relaxed flex-1 min-h-[40px]">{it.description}</p>

      {it.value && (
        <p className="text-xs text-zinc-600 mt-2 leading-relaxed border-l-2 border-gold/30 pl-2">{it.value}</p>
      )}

      {status === "keys_needed" && it.env_vars?.length > 0 && (
        <p className="text-[11px] font-mono text-amber-400/80 mt-2" data-testid={`env-vars-${it.id}`}>
          Render: {it.env_vars.join(", ")}
        </p>
      )}

      {it.provider === "quickbooks" && it.connected && lastSynced && (
        <p className="text-xs text-zinc-600 mt-2 flex items-center gap-1" data-testid="qb-last-synced">
          <Clock className="w-3 h-3" /> Last synced {lastSynced}
        </p>
      )}

      {it.provider === "quickbooks" && it.connected && canManage && (
        <button
          type="button"
          data-testid="sync-quickbooks-btn"
          onClick={onSync}
          disabled={qbSyncing}
          className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm py-2 transition-colors hover:bg-gold/15 disabled:opacity-60"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", qbSyncing && "animate-spin")} />
          {qbSyncing ? "Syncing…" : "Sync to Financials"}
        </button>
      )}

      {!isComingSoon && (
        <button
          data-testid={`action-${it.id}`}
          onClick={primaryAction}
          disabled={isComingSoon || (isOAuth && !canManage && !it.connected)}
          className={cn(
            "mt-4 w-full inline-flex items-center justify-center gap-1.5 rounded-md text-sm py-2 transition-colors disabled:opacity-50",
            isOAuth && it.connected
              ? "border border-white/10 text-zinc-400 hover:bg-white/5"
              : status === "keys_needed"
                ? "border border-amber-400/30 text-amber-400 hover:bg-amber-400/10"
                : "bg-gold text-black font-medium hover:bg-gold-hover",
          )}
        >
          {isOAuth && !it.connected && status !== "keys_needed" && <ExternalLink className="w-3.5 h-3.5" />}
          {!isOAuth && it.cta_route && <ArrowRight className="w-3.5 h-3.5" />}
          {primaryLabel()}
        </button>
      )}
    </GlassCard>
  );
}

export default function Integrations() {
  const { data, loading, error, reload } = useFetch("/integrations");
  const [params, setParams] = useSearchParams();
  const [qbSyncing, setQbSyncing] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (params.get("connected")) {
      const name = params.get("connected") === "google" ? "Google Calendar" : params.get("connected");
      toast.success(`${name} connected`);
      setParams({});
      reload();
    } else if (params.get("error")) {
      toast.error("Connection failed. Check OAuth credentials on Render and try again.");
      setParams({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  if (loading) return <LoadingScreen label="Loading integrations" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load integrations"
        message={fetchErrorMessage(error, "Integrations data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }

  const gate = () => {
    if (!data.can_manage) {
      toast.error("Only workspace owners can manage integrations");
      return false;
    }
    return true;
  };

  const oauthConnect = async (provider) => {
    if (!gate()) return;
    try {
      const { data: res } = await api.get(`/integrations/${provider}/connect`);
      if (res.configured && res.authorization_url) {
        window.location.href = res.authorization_url;
      } else {
        toast.info(res.message || "OAuth credentials not configured yet — add them on Render.");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start connection");
    }
  };

  const oauthDisconnect = async (provider) => {
    if (!gate()) return;
    try {
      await api.post(`/integrations/${provider}/disconnect`);
      reload();
      toast.success("Disconnected");
    } catch {
      toast.error("Could not disconnect");
    }
  };

  const syncQuickBooks = async () => {
    if (!gate()) return;
    setQbSyncing(true);
    try {
      const { data: res } = await api.post("/integrations/quickbooks/sync", {}, { timeout: 120000 });
      toast.success(`Synced ${res.synced_count} transaction${res.synced_count === 1 ? "" : "s"} to Financials`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "QuickBooks sync failed");
      if (e?.response?.status === 401) reload();
    } finally {
      setQbSyncing(false);
    }
  };

  const dayOne = data.integrations.filter((i) => !i.coming_soon);
  const later = data.integrations.filter((i) => i.coming_soon);

  return (
    <div>
      <PageHeader
        title="Integrations"
        subtitle="Connect the tools that feed your cockpit on day one — calendar, books, AI, and team email."
      />

      <p className="text-sm text-zinc-500 mb-6 max-w-2xl">
        OAuth connections are per-workspace. Platform keys (Anthropic, R2, Resend) are set once on Render and apply to all workspaces.
      </p>

      <h2 className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">Day 1 essentials</h2>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mb-10">
        {dayOne.map((it) => (
          <IntegrationCard
            key={it.id}
            it={it}
            canManage={data.can_manage}
            onConnect={oauthConnect}
            onDisconnect={oauthDisconnect}
            onSync={syncQuickBooks}
            onNavigate={(route) => navigate(route)}
            qbSyncing={qbSyncing}
          />
        ))}
      </div>

      {later.length > 0 && (
        <>
          <h2 className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">On the roadmap</h2>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {later.map((it) => (
              <IntegrationCard
                key={it.id}
                it={it}
                canManage={data.can_manage}
                onConnect={oauthConnect}
                onDisconnect={oauthDisconnect}
                onSync={syncQuickBooks}
                onNavigate={(route) => navigate(route)}
                qbSyncing={qbSyncing}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
