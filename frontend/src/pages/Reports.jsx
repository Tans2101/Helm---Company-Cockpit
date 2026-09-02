import { useState } from "react";
import { toast } from "sonner";
import { FileText, Sparkles, Download } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen, EmptyState } from "@/components/kit";

export default function Reports() {
  const { data, loading, error, reload } = useFetch("/reports");
  const [pack, setPack] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) return <LoadingScreen label="Loading reports" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load reports"
        message={fetchErrorMessage(error, "Reports data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }
  if (data.reports.length === 0) return <div><PageHeader title="Reports" subtitle="Sales, production and procurement — plus the AI Weekly CEO Pack." /><EmptyState title="No reports yet" body="Reports build as your data and integrations come online." /></div>;

  const generatePack = async () => {
    setBusy(true);
    try {
      const { data: res } = await api.post("/reports/weekly-pack");
      setPack(res.content);
      toast.success("Weekly CEO Pack ready");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate Weekly CEO Pack");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Reports" subtitle="Sales, production and procurement at a glance — plus the AI-generated Weekly CEO Pack." />

      <div className="grid md:grid-cols-3 gap-4 mb-6">
        {data.reports.map((r, i) => (
          <GlassCard key={r.id} className="p-5 fade-up" style={{ animationDelay: `${i*60}ms` }} data-testid={`report-${r.id}`}>
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-gold" />
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">{r.type} · {r.period}</span>
            </div>
            <h3 className="text-white font-medium">{r.title}</h3>
            <p className="text-sm text-zinc-500 mt-2 leading-relaxed">{r.summary}</p>
            <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-white/5">
              {r.metrics.map((m) => (
                <div key={m.label}>
                  <p className="font-mono text-lg text-white">{m.value}</p>
                  <p className="text-[10px] text-zinc-600 uppercase tracking-wide">{m.label}</p>
                </div>
              ))}
            </div>
          </GlassCard>
        ))}
      </div>

      <GlassCard glow className="p-6 fade-up border-gold/20">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <SectionLabel>Weekly CEO Pack</SectionLabel>
            </div>
            <p className="text-sm text-zinc-400 max-w-xl">A board-ready weekly summary — growth, financial health, risks and this week's focus — synthesized from all your data.</p>
          </div>
          <button data-testid="generate-pack-btn" onClick={generatePack} disabled={busy}
            className="inline-flex items-center gap-2 rounded-md bg-gold text-black text-sm font-medium px-4 py-2.5 transition-colors hover:bg-gold-hover disabled:opacity-60 shrink-0">
            <Sparkles className="w-4 h-4" />{busy ? "Generating…" : "Generate Pack"}
          </button>
        </div>
        {pack && (
          <div className="mt-4 rounded-lg border border-white/5 bg-black/30 p-5" data-testid="pack-content">
            <pre className="whitespace-pre-wrap font-sans text-sm text-zinc-200 leading-relaxed">{pack}</pre>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
