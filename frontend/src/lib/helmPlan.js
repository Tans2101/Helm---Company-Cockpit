/** User-facing plan labels — internal DB may still use "free" / "pro". */
export function helmPlanLabel(plan, isPro, billingEnforced = true) {
  if (!billingEnforced || isPro || plan === "pro") return "Active";
  return "Preview";
}

export function helmWorkspacePlanLabel(plan, billingEnforced = true) {
  if (!billingEnforced || plan === "pro") return "Active";
  if (plan === "free") return "Preview";
  return plan || "Preview";
}

/** Full cockpit access — false only when billing is enforced and plan is not pro. */
export function helmHasFullAccess(plan, billingEnforced = true) {
  return !billingEnforced || plan === "pro";
}
