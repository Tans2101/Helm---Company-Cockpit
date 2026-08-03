import { useState } from "react";
import { toast } from "sonner";
import { Download, Trash2, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, GlassCard } from "@/components/kit";

export default function AccountSettings() {
  const { user, logout } = useAuth();
  const isOwner = user?.role === "owner";
  const [busy, setBusy] = useState(null);

  const exportData = async () => {
    setBusy("export");
    try {
      const { data } = await api.get("/account/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `helm-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not export data");
    } finally {
      setBusy(null);
    }
  };

  const deleteAccount = async () => {
    if (!window.confirm("Delete your account permanently? This cannot be undone.")) return;
    setBusy("account");
    try {
      await api.delete("/account");
      toast.success("Account deleted");
      await logout();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete account");
      setBusy(null);
    }
  };

  const deleteWorkspace = async () => {
    if (!window.confirm("Delete this entire workspace and all its data? This cannot be undone.")) return;
    setBusy("workspace");
    try {
      await api.delete("/workspaces/current");
      toast.success("Workspace deleted");
      window.location.href = "/app";
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not delete workspace");
      setBusy(null);
    }
  };

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Account settings"
        subtitle="Export your data or permanently delete your account and workspace."
      />

      <GlassCard className="p-5 mb-4 fade-up">
        <div className="flex items-center gap-1.5 mb-2 text-gold">
          <Download className="w-4 h-4" />
          <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Export data</span>
        </div>
        <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
          Download a JSON copy of data associated with your account and active workspace.
        </p>
        <button
          data-testid="export-data-btn"
          onClick={exportData}
          disabled={!!busy}
          className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 transition-colors hover:bg-gold-hover disabled:opacity-60"
        >
          {busy === "export" ? "Exporting…" : "Export data"}
        </button>
      </GlassCard>

      <GlassCard className="p-5 mb-4 fade-up border-rose-500/20">
        <div className="flex items-center gap-1.5 mb-2 text-rose-400">
          <Trash2 className="w-4 h-4" />
          <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Delete account</span>
        </div>
        <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
          Permanently remove your user account. You will be signed out.
        </p>
        <button
          data-testid="delete-account-btn"
          onClick={deleteAccount}
          disabled={!!busy}
          className="rounded-md border border-rose-500/40 text-rose-400 text-sm font-medium px-4 py-2.5 transition-colors hover:bg-rose-500/10 disabled:opacity-60"
        >
          {busy === "account" ? "Deleting…" : "Delete account"}
        </button>
      </GlassCard>

      {isOwner && (
        <GlassCard className="p-5 fade-up border-rose-500/20">
          <div className="flex items-center gap-1.5 mb-2 text-rose-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Delete workspace</span>
          </div>
          <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
            As owner, you can permanently delete the current company workspace and all of its data for every member.
          </p>
          <button
            data-testid="delete-workspace-btn"
            onClick={deleteWorkspace}
            disabled={!!busy}
            className="rounded-md border border-rose-500/40 text-rose-400 text-sm font-medium px-4 py-2.5 transition-colors hover:bg-rose-500/10 disabled:opacity-60"
          >
            {busy === "workspace" ? "Deleting…" : "Delete workspace"}
          </button>
        </GlassCard>
      )}
    </div>
  );
}
