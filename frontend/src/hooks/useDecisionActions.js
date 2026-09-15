import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/** Shared approve / reject / delegate / suggestion actions for Decisions + My Day. */
export function useDecisionActions(reload) {
  const [busy, setBusy] = useState(null);

  const act = async (id, action, owner) => {
    setBusy(id);
    try {
      await api.post(`/decisions/${id}/action`, { action, owner });
      reload?.();
      toast.success(`Decision ${action}`);
    } catch (e) {
      toast.error("Action failed");
    } finally {
      setBusy(null);
    }
  };

  const approveSuggestion = async (id) => {
    setBusy(id);
    try {
      await api.post(`/decisions/suggestions/${id}/approve`);
      toast.success("Suggestion accepted — now a pending decision");
      reload?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not approve");
    } finally {
      setBusy(null);
    }
  };

  const dismissSuggestion = async (id) => {
    setBusy(id);
    try {
      await api.post(`/decisions/suggestions/${id}/dismiss`);
      toast.success("Suggestion dismissed");
      reload?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not dismiss");
    } finally {
      setBusy(null);
    }
  };

  return { busy, act, approveSuggestion, dismissSuggestion };
}

/** Build delegate dropdown lists from GET /members payload. */
export function buildDelegateOptions(membersData) {
  const allMembers = membersData?.members || [];
  const selfMember = allMembers.find((m) => m.is_self);
  const seenUsers = new Set();
  const delegateMembers = [];
  for (const m of allMembers) {
    if (m.is_self) continue;
    if (m.status === "invited" && !m.user_id) continue;
    const key = m.user_id || m.email;
    if (!key || seenUsers.has(key)) continue;
    seenUsers.add(key);
    delegateMembers.push(m);
  }
  const selfLabel = selfMember?.name || selfMember?.email || "Myself";
  return { selfMember, delegateMembers, selfLabel };
}
