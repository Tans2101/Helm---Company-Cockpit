import { useEffect } from "react";
import { toast } from "sonner";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Calendar, Mail, DollarSign, Github, MessageSquare, Cloud, Building2, Lock, Check, ExternalLink, KeyRound } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, ProBadge, LoadingScreen, ErrorScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const ICONS = {
  google_calendar: Calendar, gmail: Mail, paddle: DollarSign, quickbooks: Building2,
  github: Github, slack: MessageSquare, salesforce: Cloud,
};

export default function Integrations() {
  const { data, loading, error, reload } = useFetch("/integrations");
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

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

  if (loading) return <LoadingScreen label="Loading integrations" />;
  if (error || !data) return <ErrorScreen onRetry={reload} />;

  const gate = () => {
    if (!data.can_manage) { toast.error("Only workspace owners can manage integrations"); return false; }
    if (!data.is_pro) { toast.error("Live integrations require Pro"); navigate("/app/billing"); return false; }
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
                {it.pro && <ProBadge />}
                {it.oauth && <span className="text-[9px] font-mono uppercase tracking-wider text-gold/70 border border-gold/20 rounded px-1.5 py-0.5">OAuth</span>}
              </div>
              <p className="text-[11px] font-mono uppercase tracking-wide text-zinc-600 mt-0.5">{it.category}</p>
              <p className="text-sm text-zinc-500 mt-2 leading-relaxed flex-1 min-h-[40px]">{it.description}</p>
              <button data-testid={`toggle-${it.id}`} onClick={() => handleClick(it)}
                className={cn("mt-4 w-full inline-flex items-center justify-center gap-1.5 rounded-md text-sm py-2 transition-colors",
                  it.connected ? "border border-white/10 text-zinc-400 hover:bg-white/5" : "bg-gold text-black font-medium hover:bg-gold-hover")}>
                {!data.is_pro && !it.connected && <Lock className="w-3.5 h-3.5" />}
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
