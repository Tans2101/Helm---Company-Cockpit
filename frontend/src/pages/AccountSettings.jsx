import { useState } from "react";
import { toast } from "sonner";
import { Download, Trash2, AlertTriangle, ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useFetch, blobErrorDetail } from "@/hooks/useFetch";
import { PageHeader, GlassCard } from "@/components/kit";
import DepartmentsSettings from "@/components/DepartmentsSettings";

export default function AccountSettings() {
  const { user, logout } = useAuth();
  const { data: company } = useFetch("/company");
  const isOwner = user?.role === "owner" || user?.pack === "owner";
  const canExportActivity = isOwner || (user?.perms || []).includes("members:manage");
  const [busy, setBusy] = useState(null);
  const [confirmAccount, setConfirmAccount] = useState("");
  const [confirmWorkspace, setConfirmWorkspace] = useState("");
  const [showAccountConfirm, setShowAccountConfirm] = useState(false);
  const [showWorkspaceConfirm, setShowWorkspaceConfirm] = useState(false);
  const [actStart, setActStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  });
  const [actEnd, setActEnd] = useState(() => new Date().toISOString().slice(0, 10));

  const emailConfirm = (user?.email || "").trim().toLowerCase();
  const workspaceConfirm = (company?.name || "").trim();

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

  const exportActivity = async () => {
    if (!actStart || !actEnd) {
      toast.error("Choose a start and end date");
      return;
    }
    setBusy("activity");
    try {
      const res = await api.get("/activities/export", {
        params: { start: actStart, end: actEnd, format: "csv" },
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `helm-activity-${actStart}-to-${actEnd}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Activity log downloaded");
    } catch (e) {
      toast.error(await blobErrorDetail(e, "Could not export activity log"));
    } finally {
      setBusy(null);
    }
  };

  const deleteAccount = async () => {
    if (!showAccountConfirm) {
      setShowAccountConfirm(true);
      return;
    }
    if (confirmAccount.trim().toLowerCase() !== emailConfirm) {
      toast.error("Type your email exactly to confirm");
      return;
    }
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
    if (!showWorkspaceConfirm) {
      setShowWorkspaceConfirm(true);
      return;
    }
    if (confirmWorkspace.trim() !== workspaceConfirm) {
      toast.error("Type the workspace name exactly to confirm");
      return;
    }
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
        subtitle="Departments, data export, and account controls."
      />

      {isOwner && <DepartmentsSettings />}

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
        {(user?.perms || []).includes("billing:manage") && (
          <a
            href="/app/billing"
            data-testid="settings-billing-link"
            className="ml-3 inline-flex items-center rounded-md border border-white/10 text-zinc-300 text-sm px-4 py-2.5 hover:bg-white/5"
          >
            Billing
          </a>
        )}
      </GlassCard>

      {canExportActivity && (
        <GlassCard className="p-5 mb-4 fade-up" data-testid="export-activity-card">
          <div className="flex items-center gap-1.5 mb-2 text-gold">
            <ScrollText className="w-4 h-4" />
            <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Export activity log</span>
          </div>
          <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
            Download a CSV audit trail (timestamp, actor, area, action, message) for a date range. Owner/admin only.
          </p>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <label className="text-xs text-zinc-500">Start
              <input data-testid="activity-export-start" type="date" value={actStart} onChange={(e) => setActStart(e.target.value)}
                className="mt-1 w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white" />
            </label>
            <label className="text-xs text-zinc-500">End
              <input data-testid="activity-export-end" type="date" value={actEnd} onChange={(e) => setActEnd(e.target.value)}
                className="mt-1 w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white" />
            </label>
          </div>
          <button
            data-testid="export-activity-btn"
            onClick={exportActivity}
            disabled={!!busy}
            className="rounded-md border border-gold/30 bg-gold/10 text-gold font-medium text-sm px-4 py-2.5 transition-colors hover:bg-gold/15 disabled:opacity-60"
          >
            {busy === "activity" ? "Exporting…" : "Export activity log"}
          </button>
        </GlassCard>
      )}

      <GlassCard className="p-5 mb-4 fade-up border-rose-500/20">
        <div className="flex items-center gap-1.5 mb-2 text-rose-400">
          <Trash2 className="w-4 h-4" />
          <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Delete account</span>
        </div>
        <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
          Permanently remove your user account. You will be signed out.
        </p>
        {showAccountConfirm && (
          <div className="mb-4">
            <label className="block text-xs text-zinc-500 mb-1.5">
              Type <span className="text-zinc-300">{user?.email}</span> to confirm
            </label>
            <input
              data-testid="confirm-account-input"
              value={confirmAccount}
              onChange={(e) => setConfirmAccount(e.target.value)}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
              placeholder={user?.email}
            />
          </div>
        )}
        <button
          data-testid="delete-account-btn"
          onClick={deleteAccount}
          disabled={!!busy}
          className="rounded-md border border-rose-500/40 text-rose-400 text-sm font-medium px-4 py-2.5 transition-colors hover:bg-rose-500/10 disabled:opacity-60"
        >
          {busy === "account" ? "Deleting…" : showAccountConfirm ? "Confirm delete account" : "Delete account"}
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
          {showWorkspaceConfirm && (
            <div className="mb-4">
              <label className="block text-xs text-zinc-500 mb-1.5">
                Type <span className="text-zinc-300">{company?.name || "workspace name"}</span> to confirm
              </label>
              <input
                data-testid="confirm-workspace-input"
                value={confirmWorkspace}
                onChange={(e) => setConfirmWorkspace(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white"
                placeholder={company?.name}
              />
            </div>
          )}
          <button
            data-testid="delete-workspace-btn"
            onClick={deleteWorkspace}
            disabled={!!busy}
            className="rounded-md border border-rose-500/40 text-rose-400 text-sm font-medium px-4 py-2.5 transition-colors hover:bg-rose-500/10 disabled:opacity-60"
          >
            {busy === "workspace" ? "Deleting…" : showWorkspaceConfirm ? "Confirm delete workspace" : "Delete workspace"}
          </button>
        </GlassCard>
      )}
    </div>
  );
}
