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
  xero: Building2,
  hubspot: Cloud,
  github: Github,
  slack: MessageSquare,
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

function IntegrationCard({ it, canManage, onConnect, onDisconnect, onSync, onNavigate, syncingProvider }) {
  const Icon = ICONS[it.id] || Cloud;
  const status = it.status || (it.connected ? "connected" : "not_connected");
  const lastSynced = it.sync_action ? formatLastSynced(it.last_synced_at) : null;
  const isComingSoon = it.coming_soon || status === "coming_soon";
  const isUnavailable = status === "unavailable";
  const isOAuth = it.kind === "oauth" && it.oauth;
  const syncBusy = syncingProvider === it.provider;

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

      {it.connected && it.tenant_name && (
        <p className="text-xs text-zinc-500 mt-2" data-testid={`${it.id}-tenant-name`}>
          Organisation: <span className="text-zinc-300">{it.tenant_name}</span>
        </p>
      )}

      {isUnavailable && (
        <p className="text-xs text-zinc-600 mt-3 leading-relaxed" data-testid={`${it.id}-unavailable-hint`}>
          This connection isn’t available for your workspace yet. Try again later, or use Helm without it.
        </p>
      )}

      {it.sync_action && it.connected && lastSynced && (
        <p className="text-xs text-zinc-600 mt-3 flex items-center gap-1" data-testid={`${it.id}-last-synced`}>
          <Clock className="w-3 h-3" /> Last synced {lastSynced}
        </p>
      )}

      {it.sync_action && it.connected && canManage && (
        <button
          type="button"
          data-testid={`sync-${it.id}-btn`}
          onClick={() => onSync(it.provider)}
          disabled={syncBusy}
          className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm py-2 hover:bg-gold/15 disabled:opacity-60"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", syncBusy && "animate-spin")} />
          {syncBusy
            ? "Syncing…"
            : it.provider === "hubspot"
              ? "Sync to Pipeline"
              : "Sync to Financials"}
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

      {!isComingSoon && !(it.id === "gmail" && it.connected) && (
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
  const [syncingProvider, setSyncingProvider] = useState(null);
  const [slackUrl, setSlackUrl] = useState("");
  const [slackBusy, setSlackBusy] = useState(false);
  const [xeroTenantBusy, setXeroTenantBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (params.get("connected")) {
      const connected = params.get("connected");
      const name = connected === "google"
        ? "Google (Calendar & Gmail)"
        : connected === "quickbooks"
          ? "QuickBooks"
          : connected === "xero"
            ? "Xero"
            : connected === "hubspot"
              ? "HubSpot"
            : connected;
      toast.success(`${name} connected — your data will flow into Helm`);
      setParams({});
      reload();
    } else if (params.get("xero_select")) {
      toast.message("Choose which Xero organisation to sync");
      setParams({});
      reload();
    } else if (params.get("error")) {
      const err = params.get("error");
      toast.error(
        err === "xero_org"
          ? "No Xero organisations were available on that account."
          : "Could not complete the connection. Try again or use a different account.",
      );
      setParams({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  useEffect(() => {
    if (data?.slack_webhook_url != null) setSlackUrl(data.slack_webhook_url || "");
  }, [data?.slack_webhook_url]);

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

  const syncAccounting = async (provider) => {
    if (!gate()) return;
    setSyncingProvider(provider);
    try {
      const { data: res } = await api.post(`/integrations/${provider}/sync`, {}, { timeout: 120000 });
      const label = provider === "xero" ? "Xero" : provider === "hubspot" ? "HubSpot" : "QuickBooks";
      const unit = provider === "hubspot" ? "deal" : "transaction";
      toast.success(`Synced ${res.synced_count} ${unit}${res.synced_count === 1 ? "" : "s"} from ${label}`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${provider} sync failed`);
      if (e?.response?.status === 401) reload();
    } finally {
      setSyncingProvider(null);
    }
  };

  const selectXeroTenant = async (tenantId) => {
    if (!gate()) return;
    setXeroTenantBusy(true);
    try {
      const { data: res } = await api.post("/integrations/xero/select-tenant", { tenant_id: tenantId });
      toast.success(`Xero organisation selected: ${res.tenant_name || "done"}`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not select organisation");
    } finally {
      setXeroTenantBusy(false);
    }
  };

  const saveSlackWebhook = async () => {
    if (!gate()) return;
    setSlackBusy(true);
    try {
      await api.put("/integrations/slack-webhook", { webhook_url: slackUrl.trim() });
      toast.success(slackUrl.trim() ? "Slack webhook saved" : "Slack webhook cleared");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save webhook");
    } finally {
      setSlackBusy(false);
    }
  };

  const connectable = data.integrations.filter((i) => i.kind === "oauth" && !i.coming_soon);
  const roadmap = data.integrations.filter((i) => i.coming_soon);
  const connectedCount = connectable.filter((i) => i.connected).length;

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

      {data.can_manage && (data.xero_pending_tenants || []).length > 0 && (
        <GlassCard className="p-5 mb-8 fade-up border-gold/20" data-testid="xero-tenant-picker">
          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-2">Choose Xero organisation</p>
          <p className="text-sm text-zinc-400 mb-4 leading-relaxed">
            Your Xero login can access more than one organisation. Pick which one Helm should sync into Financials.
          </p>
          <div className="space-y-2">
            {data.xero_pending_tenants.map((t) => (
              <button
                key={t.tenant_id}
                type="button"
                data-testid={`xero-tenant-${t.tenant_id}`}
                disabled={xeroTenantBusy}
                onClick={() => selectXeroTenant(t.tenant_id)}
                className="w-full text-left rounded-md border border-white/10 bg-white/[0.02] px-4 py-3 hover:border-gold/40 hover:bg-white/[0.04] disabled:opacity-60"
              >
                <span className="text-sm text-white">{t.tenant_name}</span>
                <span className="block text-[10px] font-mono text-zinc-600 mt-0.5">{t.tenant_id}</span>
              </button>
            ))}
          </div>
        </GlassCard>
      )}

      <h2 className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">Connect your accounts</h2>
      <div className="grid md:grid-cols-2 gap-4 mb-10">
        {data.can_manage && (
          <GlassCard className="p-5 fade-up flex flex-col" data-testid="slack-webhook-card">
            <div className="flex items-start justify-between mb-3">
              <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-gold" />
              </div>
              <StatusBadge status={data.slack_webhook_configured ? "connected" : "not_connected"} />
            </div>
            <h3 className="text-white font-medium">Slack</h3>
            <p className="text-[11px] font-mono uppercase tracking-wide text-zinc-600 mt-0.5">Alerts</p>
            <p className="text-sm text-zinc-500 mt-2 leading-relaxed flex-1 min-h-[40px]">
              Paste a Slack Incoming Webhook URL to post high-severity Helm alerts to a channel. Leave blank to disable.
            </p>
            <label className="text-xs text-zinc-500 block mt-3">
              Incoming webhook URL
              <input
                data-testid="slack-webhook-input"
                value={slackUrl}
                onChange={(e) => setSlackUrl(e.target.value)}
                placeholder="https://hooks.slack.com/services/…"
                className="mt-1 w-full rounded-md border border-white/10 bg-helm-card text-white text-sm px-3 py-2 focus:outline-none focus:border-gold/40"
              />
            </label>
            <div className="mt-4 flex items-center gap-2">
              <button
                type="button"
                data-testid="save-slack-webhook-btn"
                disabled={slackBusy}
                onClick={saveSlackWebhook}
                className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60"
              >
                {slackBusy ? "Saving…" : "Save webhook"}
              </button>
              {data.slack_webhook_configured && (
                <span className="text-xs text-emerald-400 font-mono">Configured</span>
              )}
            </div>
          </GlassCard>
        )}
        {connectable.map((it) => (
          <IntegrationCard
            key={it.id}
            it={it}
            canManage={data.can_manage}
            onConnect={oauthConnect}
            onDisconnect={oauthDisconnect}
            onSync={syncAccounting}
            onNavigate={(route) => navigate(route)}
            syncingProvider={syncingProvider}
          />
        ))}
      </div>

      {roadmap.length > 0 && (
        <>
          <h2 className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-3">Coming soon</h2>
          <p className="text-sm text-zinc-600 mb-4 max-w-2xl">More connections on the way — engineering tools next.</p>
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
            {roadmap.map((it) => (
              <IntegrationCard
                key={it.id}
                it={it}
                canManage={data.can_manage}
                onConnect={oauthConnect}
                onDisconnect={oauthDisconnect}
                onSync={syncAccounting}
                onNavigate={(route) => navigate(route)}
                syncingProvider={syncingProvider}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
