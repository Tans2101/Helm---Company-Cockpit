import { useState } from "react";
import { toast } from "sonner";
import { UserPlus, User, Trash2, Mail, Copy, Link2, Shield } from "lucide-react";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, GlassCard, SectionLabel, LoadingScreen, ErrorScreen } from "@/components/kit";
import { PACKS, packMeta, hasPerm } from "@/lib/access";
import { DEFAULT_DEPARTMENTS } from "@/lib/departments";
import { cn } from "@/lib/utils";

export default function Members() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch("/members");
  const canInvite = hasPerm(user, "members:invite");
  const canManageOwners = hasPerm(user, "members:manage");
  const { data: codeData } = useFetch(canInvite ? "/workspaces/join-code" : null);
  const { data: accessData, reload: reloadAccess } = useFetch(canManageOwners ? "/access/sections" : null);

  const [tab, setTab] = useState("team");
  const [email, setEmail] = useState("");
  const [pack, setPack] = useState("member");
  const [inviteDept, setInviteDept] = useState(DEFAULT_DEPARTMENTS[0]);
  const [busy, setBusy] = useState(false);
  const [accessDraft, setAccessDraft] = useState(null);
  const [accessBusy, setAccessBusy] = useState(false);

  if (loading) return <LoadingScreen label="Loading team" />;
  if (error || !data) {
    return (
      <ErrorScreen
        label="Could not load team"
        message={fetchErrorMessage(error, "Team data is unavailable right now.")}
        onRetry={reload}
      />
    );
  }

  const packOptions = PACKS.filter((p) => p.id !== "owner" || canManageOwners);
  const sections = accessData?.sections || [];
  const sectionAccess = accessDraft ?? accessData?.section_access ?? {};

  const invite = async () => {
    if (!email.trim()) return;
    setBusy(true);
    try {
      const { data: res } = await api.post("/members/invite", { email: email.trim(), pack, department: inviteDept });
      toast.success(res.auto_joined ? "Member added instantly" : res.email_sent ? "Invitation email sent" : "Invitation created");
      setEmail("");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not invite");
    } finally {
      setBusy(false);
    }
  };

  const changePack = async (m, newPack, department) => {
    try {
      await api.patch(`/members/${m.membership_id}`, { pack: newPack, department });
      reload();
      toast.success("Access updated");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const remove = async (m) => {
    try { await api.delete(`/members/${m.membership_id}`); reload(); toast.success("Member removed"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const copyCode = () => {
    if (codeData?.join_code) { navigator.clipboard?.writeText(codeData.join_code); toast.success("Invite code copied"); }
  };

  const toggleDept = (sectionId, dept) => {
    const current = sectionAccess[sectionId] || [];
    const next = current.includes(dept) ? current.filter((d) => d !== dept) : [...current, dept];
    setAccessDraft({ ...sectionAccess, [sectionId]: next });
  };

  const saveAccess = async () => {
    setAccessBusy(true);
    try {
      await api.patch("/access/sections", { section_access: sectionAccess });
      toast.success("Section access saved");
      setAccessDraft(null);
      reloadAccess();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
    finally { setAccessBusy(false); }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Team & Access" subtitle="Invite teammates with access packs, assign departments, and control which departments can edit each section." />

      {canManageOwners && (
        <div className="flex gap-1 mb-6 p-1 rounded-lg border border-white/10 bg-white/[0.02] w-fit">
          {[{ id: "team", label: "Team" }, { id: "access", label: "Manage Access" }].map((t) => (
            <button key={t.id} type="button" data-testid={`tab-${t.id}`} onClick={() => setTab(t.id)}
              className={cn("px-4 py-2 text-sm rounded-md transition-colors", tab === t.id ? "bg-gold/15 text-gold" : "text-zinc-400 hover:text-white")}>
              {t.label}
            </button>
          ))}
        </div>
      )}

      {tab === "access" && canManageOwners && (
        <GlassCard className="p-5 mb-6 fade-up" data-testid="manage-access-panel">
          <div className="flex items-center gap-2 mb-2 text-gold">
            <Shield className="w-4 h-4" />
            <SectionLabel>Department section access</SectionLabel>
          </div>
          <p className="text-sm text-zinc-500 mb-5">Choose which departments can edit each area — on top of their access pack. Owners always have full access.</p>
          <div className="space-y-5">
            {sections.map((section) => (
              <div key={section.id} className="border-b border-white/5 pb-4 last:border-0">
                <p className="text-white text-sm font-medium">{section.label}</p>
                <p className="text-xs text-zinc-600 mb-2">{section.description}</p>
                <div className="flex flex-wrap gap-2">
                  {DEFAULT_DEPARTMENTS.map((dept) => {
                    const on = (sectionAccess[section.id] || []).includes(dept);
                    return (
                      <button
                        key={dept}
                        type="button"
                        data-testid={`access-${section.id}-${dept}`}
                        onClick={() => toggleDept(section.id, dept)}
                        className={cn("text-xs rounded-full px-2.5 py-1 border transition-colors", on ? "border-gold/40 bg-gold/10 text-gold" : "border-white/10 text-zinc-500 hover:border-white/20")}
                      >
                        {dept}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <button data-testid="save-access-btn" onClick={saveAccess} disabled={accessBusy}
            className="mt-5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60">
            {accessBusy ? "Saving…" : "Save access rules"}
          </button>
        </GlassCard>
      )}

      {tab === "team" && (
        <>
          {canInvite && (
            <GlassCard className="p-5 mb-4 fade-up">
              <div className="flex items-center gap-1.5 mb-3 text-gold">
                <UserPlus className="w-4 h-4" />
                <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Invite a teammate</span>
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="flex items-center gap-2 flex-1 rounded-md border border-white/10 bg-[#141417] px-3 focus-within:border-gold/40">
                  <Mail className="w-4 h-4 text-zinc-600" />
                  <input data-testid="invite-email-input" value={email} onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && invite()} placeholder="teammate@company.com"
                    className="flex-1 bg-transparent text-white text-sm placeholder:text-zinc-600 focus:outline-none py-2.5" />
                </div>
                <select data-testid="invite-dept-select" value={inviteDept} onChange={(e) => setInviteDept(e.target.value)}
                  className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40">
                  {DEFAULT_DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <select data-testid="invite-pack-select" value={pack} onChange={(e) => setPack(e.target.value)}
                  className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40">
                  {packOptions.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
                <button data-testid="invite-submit-btn" onClick={invite} disabled={busy}
                  className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover disabled:opacity-60">
                  {busy ? "Inviting…" : "Invite"}
                </button>
              </div>
              <p className="text-xs text-zinc-500 mt-2.5" data-testid="pack-desc">{packMeta(pack).label} · {inviteDept} — {packMeta(pack).desc}</p>
            </GlassCard>
          )}

          {canInvite && codeData?.join_code && (
            <GlassCard className="p-4 mb-6 fade-up flex items-center gap-3" data-testid="join-code-card">
              <Link2 className="w-4 h-4 text-gold shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-zinc-400">Open invite code — share to let anyone join as a Member</p>
                <p className="font-mono text-lg text-white tracking-[0.3em] mt-0.5" data-testid="join-code-value">{codeData.join_code}</p>
              </div>
              <button data-testid="copy-join-code" onClick={copyCode} className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-2 hover:bg-white/5"><Copy className="w-3.5 h-3.5" /> Copy</button>
            </GlassCard>
          )}

          <div className="space-y-2">
            {data.members.map((m) => {
              const meta = packMeta(m.pack || m.role);
              const targetIsOwner = (m.pack || m.role) === "owner";
              const canEditThis = canInvite && !m.is_self && (!targetIsOwner || canManageOwners);
              return (
                <GlassCard key={m.membership_id} className="p-4 fade-up" data-testid={`member-row-${m.email}`}>
                  <div className="flex items-center gap-3 flex-wrap">
                    {m.picture ? (
                      <img src={m.picture} alt="" className="w-9 h-9 rounded-full object-cover border border-white/10" />
                    ) : (
                      <div className="w-9 h-9 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                        <User className="w-4 h-4 text-zinc-500" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-white truncate">{m.name || m.email}</p>
                        {m.is_self && <span className="text-[10px] text-zinc-600">(you)</span>}
                      </div>
                      <p className="text-xs text-zinc-500 truncate">{m.email} · {m.department || "General"}</p>
                    </div>
                    {m.status === "invited" && (
                      <span className="text-[10px] font-mono uppercase tracking-wide text-amber-400 bg-amber-400/10 rounded px-2 py-1">Invited</span>
                    )}
                    <span className={cn("inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide rounded px-2 py-1 border", meta.style)}>
                      <meta.icon className="w-3 h-3" />{meta.label}
                    </span>
                    {canEditThis && (
                      <div className="flex items-center gap-1 flex-wrap">
                        <select value={m.department || "General"} onChange={(e) => changePack(m, m.pack || m.role, e.target.value)}
                          className="text-[11px] text-zinc-300 bg-[#141417] border border-white/10 rounded px-2 py-1 focus:outline-none focus:border-gold/40">
                          {DEFAULT_DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                        </select>
                        <select value={m.pack || m.role} onChange={(e) => changePack(m, e.target.value, m.department)}
                          data-testid={`pack-select-${m.email}`}
                          className="text-[11px] text-zinc-300 bg-[#141417] border border-white/10 rounded px-2 py-1 focus:outline-none focus:border-gold/40">
                          {PACKS.filter((p) => p.id !== "owner" || canManageOwners).map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                        </select>
                        {canManageOwners && (
                          <button onClick={() => remove(m)} data-testid={`remove-${m.email}`}
                            className="text-zinc-600 hover:text-rose-400 p-1.5 rounded transition-colors">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </GlassCard>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
