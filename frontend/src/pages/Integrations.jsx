import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Calendar, DollarSign, Github, MessageSquare, Cloud, Building2, Lock, Check } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, ProBadge, LoadingScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const ICONS = {
  google: Calendar, stripe: DollarSign, quickbooks: Building2,
  github: Github, slack: MessageSquare, salesforce: Cloud,
};

export default function Integrations() {
  const { data, loading, setData } = useFetch("/integrations");
  const navigate = useNavigate();
  if (loading || !data) return <LoadingScreen label="Loading integrations" />;

  const toggle = async (id) => {
    if (!data.is_pro) {
      toast.error("Live integrations require Pro");
      navigate("/billing");
      return;
    }
    try {
      const { data: res } = await api.post(`/integrations/${id}/toggle`);
      setData({ ...data, integrations: res.integrations });
    } catch (e) {
      toast.error("Could not toggle integration");
    }
  };

  return (
    <div>
      <PageHeader title="Integrations" subtitle="Kalun pulls status and KPIs in, pushes work out. Employees stay in their tools — you stay in the cockpit." />

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.integrations.map((it) => {
          const Icon = ICONS[it.id] || Cloud;
          return (
            <GlassCard key={it.id} className="p-5 fade-up" data-testid={`integration-${it.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-gold" />
                </div>
                {it.connected ? (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide text-emerald-400 bg-emerald-400/10 rounded px-2 py-1">
                    <Check className="w-3 h-3" /> Connected
                  </span>
                ) : (
                  <span className="text-[10px] font-mono uppercase tracking-wide text-zinc-600 border border-white/10 rounded px-2 py-1">Not connected</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <h3 className="text-white font-medium">{it.name}</h3>
                {it.pro && <ProBadge />}
              </div>
              <p className="text-[11px] font-mono uppercase tracking-wide text-zinc-600 mt-0.5">{it.category}</p>
              <p className="text-sm text-zinc-500 mt-2 leading-relaxed min-h-[40px]">{it.description}</p>
              <button data-testid={`toggle-${it.id}`} onClick={() => toggle(it.id)}
                className={cn("mt-4 w-full inline-flex items-center justify-center gap-1.5 rounded-md text-sm py-2 transition-colors",
                  it.connected
                    ? "border border-white/10 text-zinc-400 hover:bg-white/5"
                    : "bg-gold text-black font-medium hover:bg-gold-hover")}>
                {!data.is_pro && <Lock className="w-3.5 h-3.5" />}
                {it.connected ? "Disconnect" : "Connect"}
              </button>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
