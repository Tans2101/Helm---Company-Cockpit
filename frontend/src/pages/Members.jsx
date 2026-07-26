import { useState } from "react";
import { toast } from "sonner";
import { UserPlus, Shield, User, Trash2, Mail, Crown } from "lucide-react";
import { useFetch } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, GlassCard, LoadingScreen } from "@/components/kit";
import { cn } from "@/lib/utils";

const roleStyle = {
  owner: "text-gold bg-gold/10 border-gold/20",
  member: "text-sky-400 bg-sky-400/10 border-sky-400/20",
};

export default function Members() {
  const { data, loading, reload } = useFetch("/members");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [busy, setBusy] = useState(false);

  if (loading || !data) return <LoadingScreen label="Loading team" />;
  const isOwner = data.my_role === "owner";

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
      <PageHeader title="Team & Access" subtitle="Invite your leadership team into the same cockpit. Owners run the company; members get read access and can move work." />

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
              <option value="member">Member</option>
              <option value="owner">Owner</option>
            </select>
            <button data-testid="invite-submit-btn" onClick={invite} disabled={busy}
              className="rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 transition-colors hover:bg-gold-hover disabled:opacity-60">
              {busy ? "Inviting…" : "Invite"}
            </button>
          </div>
          <p className="text-xs text-zinc-600 mt-2">Existing Kalun users join instantly. New emails join automatically the first time they sign in with Google.</p>
        </GlassCard>
      )}

      <div className="space-y-2">
        {data.members.map((m) => (
          <GlassCard key={m.membership_id} className="p-4 fade-up" data-testid={`member-row-${m.email}`}>
            <div className="flex items-center gap-3">
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
              <span className={cn("inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wide rounded px-2 py-1 border", roleStyle[m.role])}>
                {m.role === "owner" ? <Crown className="w-3 h-3" /> : <Shield className="w-3 h-3" />}{m.role}
              </span>
              {isOwner && !m.is_self && (
                <div className="flex items-center gap-1">
                  <button onClick={() => changeRole(m, m.role === "owner" ? "member" : "owner")}
                    data-testid={`role-toggle-${m.email}`}
                    className="text-[11px] text-zinc-500 hover:text-gold px-2 py-1 rounded transition-colors">
                    Make {m.role === "owner" ? "member" : "owner"}
                  </button>
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
