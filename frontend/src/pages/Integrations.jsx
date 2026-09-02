import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useSearchParams } from "react-router-dom";
import { Calendar, Mail, DollarSign, Github, MessageSquare, Cloud, Building2, Check, ExternalLink, KeyRound, RefreshCw } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const ICONS = {
  google_calendar: Calendar, gmail: Mail, stripe: DollarSign, quickbooks: Building2,
  github: Github, slack: MessageSquare, salesforce: Cloud,
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

export default function Integrations() {
  const { data, loading, reload } = useFetch("/integrations");
  const [params, setParams] = useSearchParams();
  const [qbSyncing, setQbSyncing] = useState(false);

  useEffect(() => {
    if (params.get("connected")) {
      toast.success(`${params.get("connected")} connected`);
      setParams({});
      reload();
    } else if (params.get("error")) {
      toast.error("Connection failed. Check credentials and try again.");
      setParams({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  if (loading || !data) return <LoadingScreen label="Loading integrations" />;

  const gate = () => {
    if (!data.can_manage) { toast.error("Only workspace owners can manage integrations"); return false; }
    return true;
  };

  const oauthConnect = async (provider) => {
    if (!gate()) return;
    try {
      const { data: res } = await api.get(`/integrations/${provider}/connect`);
      if (res.configured && res.authorization_url) {
        window.location.href = res.authorization_url;
      } else {
        toast.info(res.message || "OAuth credentials not configured yet.");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start connection");
    }
  };

  const oauthDisconnect = async (provider) => {
    if (!gate()) return;
    try { await api.post(`/integrations/${provider}/disconnect`); reload(); toast.success("Disconnected"); }
    catch (e) { toast.error("Could not disconnect"); }
  };

  const syncQuickBooks = async () => {
    if (!gate()) return;
    setQbSyncing(true);
    try {
      const { data: res } = await api.post("/integrations/quickbooks/sync", {}, { timeout: 120000 });
      toast.success(`Synced ${res.synced_count} transaction${res.synced_count === 1 ? "" : "s"} from QuickBooks`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "QuickBooks sync failed");
      if (e?.response?.status === 401) reload();
    } finally {
      setQbSyncing(false);
    }
  };

  const toggleData = async (id) => {
    if (!gate()) return;
    try { await api.post(`/integrations/${id}/toggle`); reload(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not toggle"); }
  };

  const handleClick = (it) => {
    if (it.oauth) {
      it.connected ? oauthDisconnect(it.provider) : oauthConnect(it.provider);
    } else {
      toggleData(it.id);
    }
  };

  return (
    <div>
      <PageHeader title="Integrations" subtitle="Helm pulls status and KPIs in, pushes work out. Employees stay in their tools — you stay in the cockpit." />

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.integrations.map((it) => {
          const Icon = ICONS[it.id] || Cloud;
          const needsKeys = it.oauth && it.configured === false;
          const lastSynced = it.provider === "quickbooks" ? formatLastSynced(it.last_synced_at) : null;
          return (
            <GlassCard key={it.id} className="p-5 fade-up flex flex-col" data-testid={`integration-${it.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-gold" />
                </div>
                {it.connected ? (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide text-emerald-400 bg-emerald-400/10 rounded px-2 py-1">
                    <Check className="w-3 h-3" /> Connected
                  </span>
                ) : needsKeys ? (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide text-amber-400 bg-amber-400/10 rounded px-2 py-1">
                    <KeyRound className="w-3 h-3" /> Keys needed
                  </span>
                ) : (
                  <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-600 border border-white/10 rounded px-2 py-1">Not connected</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <h3 className="text-white font-medium">{it.name}</h3>
                {it.oauth && <span className="text-[9px] font-mono uppercase tracking-wider text-gold/70 border border-gold/20 rounded px-1.5 py-0.5">OAuth</span>}
              </div>
              <p className="text-[11px] font-mono uppercase tracking-wide text-zinc-600 mt-0.5">{it.category}</p>
              <p className="text-sm text-zinc-500 mt-2 leading-relaxed flex-1 min-h-[40px]">{it.description}</p>
              {it.provider === "quickbooks" && it.connected && lastSynced && (
                <p className="text-xs text-zinc-600 mt-2" data-testid="qb-last-synced">
                  Last synced {lastSynced}
                </p>
              )}
              {it.provider === "quickbooks" && it.connected && (
                <button
                  type="button"
                  data-testid="sync-quickbooks-btn"
                  onClick={syncQuickBooks}
                  disabled={qbSyncing}
                  className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-gold/30 bg-gold/10 text-gold text-sm py-2 transition-colors hover:bg-gold/15 disabled:opacity-60"
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", qbSyncing && "animate-spin")} />
                  {qbSyncing ? "Syncing…" : "Sync now"}
                </button>
              )}
              <button data-testid={`toggle-${it.id}`} onClick={() => handleClick(it)}
                className={cn("mt-4 w-full inline-flex items-center justify-center gap-1.5 rounded-md text-sm py-2 transition-colors",
                  it.connected ? "border border-white/10 text-zinc-400 hover:bg-white/5" : "bg-gold text-black font-medium hover:bg-gold-hover")}>
                {it.oauth && !it.connected && <ExternalLink className="w-3.5 h-3.5" />}
                {it.connected ? "Disconnect" : needsKeys ? "Set up" : "Connect"}
              </button>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
