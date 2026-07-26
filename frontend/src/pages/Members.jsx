import { useState } from "react";
import { toast } from "sonner";
import { UserPlus, Shield, User, Trash2, Mail, Crown, Briefcase } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen } from "@/components/kit";
import { cn } from "@/lib/utils";
import { PACK_LABELS } from "@/lib/access";

const PACKS = ["owner", "exec", "finance", "hr", "sales", "ops", "member"];

const roleStyle = {
  owner: "text-gold bg-gold/10 border-gold/20",
  exec: "text-violet-300 bg-violet-400/10 border-violet-400/20",
  finance: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  hr: "text-amber-300 bg-amber-400/10 border-amber-400/20",
  sales: "text-sky-300 bg-sky-400/10 border-sky-400/20",
  ops: "text-orange-300 bg-orange-400/10 border-orange-400/20",
  member: "text-sky-400 bg-sky-400/10 border-sky-400/20",
};

function RoleIcon({ role }) {
  if (role === "owner") return <Crown className="w-3 h-3" />;
  if (["finance", "hr", "sales", "ops"].includes(role)) return <Briefcase className="w-3 h-3" />;
  return <Shield className="w-3 h-3" />;
}

export default function Members() {
  const { data, loading, reload } = useFetch("/members");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("finance");
  const [busy, setBusy] = useState(false);

  if (loading || !data) return <LoadingScreen label="Loading team" />;
  const isOwner = data.my_role === "owner";
  const packs = data.packs?.length ? data.packs : PACKS;

  const invite = async () => {
    if (!email.trim()) return;
    setBusy(true);
    try {
      const { data: res } = await api.post("/members/invite", { email: email.trim(), role });
      toast.success(res.auto_joined ? "Member added instantly" : res.email_sent ? "Invitation email sent" : "Invitation created — they'll join on first sign-in");
      setEmail("");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not invite");
    } finally {
      setBusy(false);
    }
  };

  const changeRole = async (m, newRole) => {
    try { await api.patch(`/members/${m.membership_id}`, { role: newRole }); reload(); toast.success("Role updated"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const remove = async (m) => {
    try { await api.delete(`/members/${m.membership_id}`); reload(); toast.success("Member removed"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Team & Access" subtitle="Invite teammates with an access pack — Finance, HR, Sales, and Ops write their lane; Executives see the full cockpit; Owner runs the company." />

      {isOwner && (
        <GlassCard className="p-5 mb-6 fade-up">
          <div className="flex items-center gap-1.5 mb-3 text-gold">
            <UserPlus className="w-4 h-4" />
            <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Invite a teammate</span>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex items-center gap-2 flex-1 rounded-md border border-white/10 bg-[#141417] px-3 focus-within:border-gold/40 transition-colors">
              <Mail className="w-4 h-4 text-zinc-600" />
              <input data-testid="invite-email-input" value={email} onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && invite()} placeholder="teammate@company.com"
                className="flex-1 bg-transparent text-white text-sm placeholder:text-zinc-600 focus:outline-none py-2.5" />
            </div>
            <select data-testid="invite-role-select" value={role} onChange={(e) => setRole(e.target.value)}
              className="rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40">
              {packs.map((p) => (
                <option key={p} value={p}>{PACK_LABELS[p] || p}</option>
              ))}
            </select>
            <button data-testid="invite-submit-btn" onClick={invite} disabled={busy}
              className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 transition-colors hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Inviting…" : "Invite"}
            </button>
          </div>
          <p className="text-xs text-zinc-600 mt-2">Finance and HR get a focused workbench that feeds the CEO Briefing. Existing Helm users join instantly.</p>
        </GlassCard>
      )}

      <div className="space-y-2">
        {data.members.map((m) => (
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
                <p className="text-xs text-zinc-500 truncate">{m.email}</p>
              </div>
              {m.status === "invited" && (
                <span className="text-[10px] font-mono uppercase tracking-wide text-amber-400 bg-amber-400/10 rounded px-2 py-1">Invited</span>
              )}
              <span className={cn("inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide rounded px-2 py-1 border", roleStyle[m.role] || roleStyle.member)}>
                <RoleIcon role={m.role} />{PACK_LABELS[m.role] || m.role}
              </span>
              {isOwner && !m.is_self && (
                <div className="flex items-center gap-1">
                  <select
                    data-testid={`role-select-${m.email}`}
                    value={m.role}
                    onChange={(e) => changeRole(m, e.target.value)}
                    className="text-[11px] rounded border border-white/10 bg-[#141417] text-zinc-300 px-2 py-1 focus:outline-none focus:border-gold/40"
                  >
                    {packs.map((p) => (
                      <option key={p} value={p}>{PACK_LABELS[p] || p}</option>
                    ))}
                  </select>
                  <button onClick={() => remove(m)} data-testid={`remove-${m.email}`}
                    className="text-zinc-600 hover:text-rose-400 p-1.5 rounded transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
