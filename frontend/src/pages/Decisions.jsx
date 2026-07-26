import { useState } from "react";
import { toast } from "sonner";
import { Check, X, Share2, Sparkles, ShieldCheck } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, EmptyState } from "@/components/kit";
import { cn } from "@/lib/utils";

const statusStyle = {
  pending: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  approved: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  rejected: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  delegated: "text-sky-400 bg-sky-400/10 border-sky-400/20",
};

export default function Decisions() {
  const { data, loading, setData } = useFetch("/decisions");
  const [busy, setBusy] = useState(null);

  if (loading || !data) return <LoadingScreen label="Loading decisions" />;
  if (data.decisions.length === 0) return <div><PageHeader title="Decision Center" subtitle="Approvals, follow-ups and AI recommendations." /><EmptyState title="No decisions yet" body="When something needs your call, it surfaces here with an AI recommendation and confidence score." /></div>;

  const act = async (id, action, owner) => {
    setBusy(id);
    try {
      const { data: res } = await api.post(`/decisions/${id}/action`, { action, owner });
      setData({ ...data, decisions: res.decisions });
      toast.success(`Decision ${action}`);
    } catch (e) {
      toast.error("Action failed");
    } finally {
      setBusy(null);
    }
  };

  const pending = data.decisions.filter((d) => d.status === "pending");
  const resolved = data.decisions.filter((d) => d.status !== "pending");

  return (
    <div>
      <PageHeader
        title="Decision Center"
        subtitle="Approvals, follow-ups and AI recommendations with confidence scoring. Every open decision, ranked by impact."
        action={<div className="hidden md:flex items-center gap-2 text-xs font-mono text-gold"><ShieldCheck className="w-4 h-4" />{pending.length} awaiting you</div>}
      />

      <div className="space-y-4">
        {pending.map((d) => (
          <GlassCard key={d.id} className="p-5 fade-up" data-testid={`decision-${d.id}`}>
            <div className="flex flex-col lg:flex-row lg:items-start gap-5">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 border border-white/10 rounded px-1.5 py-0.5">{d.category}</span>
                  <span className={cn("text-[10px] font-mono uppercase tracking-wider rounded px-1.5 py-0.5 border", statusStyle[d.status])}>{d.status}</span>
                  <span className="text-[10px] font-mono text-zinc-600">Impact: {d.impact} · Due {d.due}</span>
                </div>
                <h3 className="text-lg text-white font-medium tracking-tight">{d.title}</h3>
                <p className="text-sm text-zinc-500 mt-1">{d.description}</p>

                <div className="mt-4 rounded-lg border border-gold/20 bg-gold/[0.04] p-3">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-gold" />
                    <span className="text-[11px] font-mono uppercase tracking-wider text-gold">Helm recommends</span>
                    <span className="ml-auto font-mono text-xs text-gold">{d.confidence}% confidence</span>
                  </div>
                  <p className="text-sm text-zinc-200 leading-relaxed">{d.recommendation}</p>
                  <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full bg-gold rounded-full" style={{ width: `${d.confidence}%` }} />
                  </div>
                </div>
              </div>

              <div className="flex lg:flex-col gap-2 lg:w-40">
                {data.can_act ? (
                  <>
                <button data-testid={`approve-${d.id}`} disabled={busy === d.id} onClick={() => act(d.id, "approved")}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-gold text-black text-sm font-medium py-2 transition-colors hover:bg-gold-hover disabled:opacity-50">
                  <Check className="w-4 h-4" /> Approve
                </button>
                <button data-testid={`delegate-${d.id}`} disabled={busy === d.id} onClick={() => act(d.id, "delegated", "Team")}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 text-white text-sm py-2 transition-colors hover:bg-white/5 disabled:opacity-50">
                  <Share2 className="w-4 h-4" /> Delegate
                </button>
                <button data-testid={`reject-${d.id}`} disabled={busy === d.id} onClick={() => act(d.id, "rejected")}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 text-zinc-400 text-sm py-2 transition-colors hover:bg-white/5 hover:text-rose-400 disabled:opacity-50">
                  <X className="w-4 h-4" /> Reject
                </button>
                  </>
                ) : (
                  <p className="text-xs text-zinc-600 lg:w-40 leading-relaxed">Only workspace owners can act on decisions.</p>
                )}
              </div>
            </div>
          </GlassCard>
        ))}
      </div>

      {resolved.length > 0 && (
        <div className="mt-8">
          <SectionLabel className="mb-4">Recently resolved · outcome checks</SectionLabel>
          <div className="space-y-2">
            {resolved.map((d) => (
              <div key={d.id} className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3" data-testid={`resolved-${d.id}`}>
                <span className={cn("text-[10px] font-mono uppercase tracking-wider rounded px-1.5 py-0.5 border", statusStyle[d.status])}>{d.status}</span>
                <span className="text-sm text-zinc-300 flex-1">{d.title}</span>
                <span className="text-xs text-zinc-600">{d.owner ? `→ ${d.owner}` : ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
