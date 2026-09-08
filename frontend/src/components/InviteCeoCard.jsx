import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Handshake } from "lucide-react";
import { api } from "@/lib/api";
import { useFetch } from "@/hooks/useFetch";
import { GlassCard } from "@/components/kit";

const STATUS_LABEL = {
  sent: "Sent",
  signed_up: "Signed up",
  converted: "Converted",
};

export default function InviteCeoCard() {
  const { data, reload } = useFetch("/referrals");
  const [shareUrl, setShareUrl] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (data?.share_url) setShareUrl(data.share_url);
  }, [data]);

  useEffect(() => {
    let cancelled = false;
    api.post("/referrals", {})
      .then((r) => {
        if (cancelled) return;
        if (r.data?.share_url) setShareUrl(r.data.share_url);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const copyLink = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Referral link copied");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy — select the link instead");
    }
  };

  const trackEmail = async () => {
    if (!email.trim()) return;
    setBusy(true);
    try {
      await api.post("/referrals", { email: email.trim() });
      setEmail("");
      toast.success("Invite recorded");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not record invite");
    } finally {
      setBusy(false);
    }
  };

  const rows = data?.referrals || [];

  return (
    <GlassCard className="p-5 mb-4 fade-up" data-testid="invite-ceo-card">
      <div className="flex items-center gap-1.5 mb-2 text-gold">
        <Handshake className="w-4 h-4" />
        <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Invite a CEO</span>
      </div>
      <p className="text-sm text-zinc-500 mb-4 leading-relaxed">
        Share Helm with another business owner you know. This is a tracking link only — no discount or credit is applied.
      </p>
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          data-testid="referral-link-input"
          readOnly
          value={shareUrl || "Generating link…"}
          className="flex-1 rounded-md border border-white/10 bg-[#141417] px-3 py-2.5 text-sm text-white font-mono truncate"
        />
        <button
          data-testid="copy-referral-link"
          type="button"
          onClick={copyLink}
          disabled={!shareUrl}
          className="inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-3 py-2.5 hover:bg-white/5 disabled:opacity-50"
        >
          <Copy className="w-3.5 h-3.5" />
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>
      <div className="flex flex-col sm:flex-row gap-2 mt-3">
        <input
          data-testid="referral-email-input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && trackEmail()}
          placeholder="Optional: their email to track this invite"
          className="flex-1 rounded-md border border-white/10 bg-[#141417] px-3 py-2.5 text-sm text-white placeholder:text-zinc-600"
        />
        <button
          data-testid="referral-track-btn"
          type="button"
          onClick={trackEmail}
          disabled={busy || !email.trim()}
          className="rounded-md border border-gold/30 bg-gold/10 text-gold font-medium text-sm px-4 py-2.5 hover:bg-gold/15 disabled:opacity-50"
        >
          {busy ? "Saving…" : "Track invite"}
        </button>
      </div>
      {rows.length > 0 && (
        <div className="mt-4 border-t border-white/5 pt-3" data-testid="referral-list">
          <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-2">Your referrals</p>
          <ul className="space-y-1.5">
            {rows.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 text-sm" data-testid="referral-row">
                <span className="text-zinc-300 truncate">{r.referred_email || "Link signup"}</span>
                <span className="shrink-0 font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                  {STATUS_LABEL[r.status] || r.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </GlassCard>
  );
}
