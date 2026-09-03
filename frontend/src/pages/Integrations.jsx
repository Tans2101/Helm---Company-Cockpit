import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Calendar, Mail, Building2, Check, ExternalLink, RefreshCw,
  Cloud, Github, MessageSquare, Clock, ArrowRight, Link2, Unlink,
} from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen, ErrorScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const ICONS = {
  google_calendar: Calendar,
  gmail: Mail,
  quickbooks: Building2,
  github: Github,
  slack: MessageSquare,
  salesforce: Cloud,
};

const STATUS_LABELS = {
  connected: { text: "Connected", className: "text-emerald-400 bg-emerald-400/10" },
  not_connected: { text: "Not connected", className: "text-zinc-400 border border-white/10" },
  unavailable: { text: "Unavailable", className: "text-zinc-500 border border-white/10" },
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
  const Icon = status === "connected" ? Check : null;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide rounded px-2 py-1", cfg.className)}>
      {Icon && <Icon className="w-3 h-3" />}
      {cfg.text}
    </span>
  );
}

function IntegrationCard({ it, canManage, onConnect, onDisconnect, onSync, onNavigate, qbSyncing }) {
  const Icon = ICONS[it.id] || Cloud;
  const status = it.status || (it.connected ? "connected" : "not_connected");
  const lastSynced = it.provider === "quickbooks" ? formatLastSynced(it.last_synced_at) : null;
  const isComingSoon = it.coming_soon || status === "coming_soon";
  const isUnavailable = status === "unavailable";
  const isOAuth = it.kind === "oauth" && it.oauth;

  const handleConnect = () => {
    if (isComingSoon || isUnavailable) return;
    if (isOAuth) {
      it.connected ? onDisconnect(it.provider) : onConnect(it.provider);
    } else if (it.cta_route) {
      onNavigate(it.cta_route);
    }
  };

  return (
    <GlassCard key={it.id} className="p-5 fade-up flex flex-col" data-testid={`integration-${it.id}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
          <Icon className="w-5 h-5 text-gold" />
        </div>
        <StatusBadge status={status} />
      </div>

      <h3 className="text-white font-medium">{it.name}</h3>
      <p className="text-[11px] font-mono uppercase tracking-wide text-zinc-600 mt-0.5">{it.category}</p>
      <p className="text-sm text-zinc-500 mt-2 leading-relaxed flex-1 min-h-[40px]">{it.description}</p>

      {it.value && (
        <p className="text-xs text-zinc-400 mt-3 leading-relaxed border-l-2 border-gold/30 pl-2">{it.value}</p>
      )}

      {isUnavailable && (
        <p className="text-xs text-zinc-600 mt-3 leading-relaxed" data-testid={`${it.id}-unavailable-hint`}>
          {it.provider === "google"
            ? "Waiting on GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET on the server. Once set, refresh and Connect works."
            : it.provider === "quickbooks"
              ? "Waiting on QUICKBOOKS_CLIENT_ID / QUICKBOOKS_CLIENT_SECRET on the server. Once set, refresh and Connect works."
              : "This connection isn’t enabled on the server yet. After the API keys are set, refresh this page."}
        </p>
      )}

      {it.provider === "quickbooks" && it.connected && lastSynced && (
        <p className="text-xs text-zinc-600 mt-3 flex items-center gap-1" data-testid="qb-last-synced">
          <Clock className="w-3 h-3" /> Last synced {lastSynced}
        </p>
      )}

      {it.provider === "quickbooks" && it.connected && canManage && (
        <button
          type="button"
          data-testid="sync-quickbooks-btn"
          onClick={onSync}
          disabled={qbSyncing}
          className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm py-2 hover:bg-gold/15 disabled:opacity-60"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", qbSyncing && "animate-spin")} />
          {qbSyncing ? "Syncing…" : "Sync to Financials"}
        </button>
      )}

      {it.connected && it.cta_route && (
        <button
          type="button"
          onClick={() => onNavigate(it.cta_route)}
          className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm py-2 hover:bg-white/5"
        >
          <ArrowRight className="w-3.5 h-3.5" /> {it.cta_label || "Open in Helm"}
        </button>
      )}

      {!isComingSoon && (
        <button
          data-testid={`action-${it.id}`}
          onClick={handleConnect}
          disabled={isComingSoon || isUnavailable || (!canManage && !it.connected)}
          className={cn(
            "mt-4 w-full inline-flex items-center justify-center gap-1.5 rounded-md text-sm py-2.5 transition-colors disabled:opacity-50",
            it.connected
              ? "border border-white/10 text-zinc-400 hover:bg-white/5"
              : isUnavailable
                ? "border border-white/10 text-zinc-600 cursor-not-allowed"
                : "bg-gold text-black font-medium hover:bg-gold-hover",
          )}
        >
          {it.connected ? (
            <><Unlink className="w-3.5 h-3.5" /> Disconnect</>
          ) : isUnavailable ? (
            <><Link2 className="w-3.5 h-3.5" /> Connect unavailable</>
          ) : (
            <><ExternalLink className="w-3.5 h-3.5" /> {it.connect_label || `Connect ${it.name}`}</>
          )}
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
      const name = params.get("connected") === "google" ? "Google Calendar" : params.get("connected") === "quickbooks" ? "QuickBooks" : params.get("connected");
      toast.success(`${name} connected — your data will flow into Helm`);
      setParams({});
      reload();
    } else if (params.get("error")) {
      toast.error("Could not complete the connection. Try again or use a different account.");
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
      toast.error("Only workspace owners can connect integrations");
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
        toast.info(res.message || "This connection isn't available yet on your Helm instance.");
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

  const connectable = data.integrations.filter((i) => i.kind === "oauth" && !i.coming_soon);
  const roadmap = data.integrations.filter((i) => i.coming_soon);
  const connectedCount = connectable.filter((i) => i.connected).length;
  const platform = data.platform || {};
  const showPlatform = data.can_manage;

  return (
    <div>
      <PageHeader
        title="Integrations"
        subtitle="Connect your calendar, accounting, and tools — Helm pulls your data in so the briefing, financials, and calendar stay current."
      />

      <GlassCard className="p-4 mb-8 fade-up border-white/5">
        <p className="text-sm text-zinc-400 leading-relaxed">
          Each connection is <span className="text-zinc-200">per company workspace</span> and uses secure OAuth —
          Helm never sees your passwords. Owners connect accounts here; teammates see the results in Calendar and Financials.
          {connectedCount > 0 && (
            <span className="text-emerald-400/90"> {connectedCount} connected.</span>
          )}
        </p>
      </GlassCard>

      {showPlatform && (
        <GlassCard className="p-4 mb-8 fade-up" data-testid="platform-readiness">
          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">Server readiness</p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs">
            {[
              ["Google Calendar OAuth", platform.google],
              ["QuickBooks OAuth", platform.quickbooks],
              ["Anthropic AI", platform.anthropic],
              ["Document storage (R2)", platform.r2],
              ["Invite email (Resend)", platform.resend],
              ["Paddle billing", platform.paddle_ready],
            ].map(([label, ok]) => (
              <div key={label} className="flex items-center justify-between gap-2 rounded-md border border-white/5 bg-white/[0.02] px-3 py-2">
                <span className="text-zinc-400">{label}</span>
                <span className={ok ? "text-emerald-400 font-mono" : "text-zinc-600 font-mono"}>{ok ? "ready" : "needs key"}</span>
              </div>
            ))}
          </div>
          {!platform.google || !platform.quickbooks ? (
            <p className="text-[11px] text-zinc-600 mt-3 leading-relaxed">
              Add missing keys on Render, redeploy, then refresh. Redirect URIs must be{" "}
              <span className="font-mono text-zinc-500">https://www.helmcontrol.online/api/oauth/…/callback</span>
              {" "}(see INTEGRATIONS.md).
            </p>
          ) : null}
        </GlassCard>
      )}

      <h2 className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">Connect your accounts</h2>
      <div className="grid md:grid-cols-2 gap-4 mb-10">
        {connectable.map((it) => (
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

      {roadmap.length > 0 && (
        <>
          <h2 className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">Coming soon</h2>
          <p className="text-sm text-zinc-600 mb-4 max-w-2xl">More connections on the way — email, engineering, comms, and CRM.</p>
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
            {roadmap.map((it) => (
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
