/** User-facing plan labels — internal DB may still use "free" / "pro". */
export function helmPlanLabel(plan, isPro) {
  if (isPro || plan === "pro") return "Active";
  return "Preview";
}

export function helmWorkspacePlanLabel(plan) {
  if (plan === "pro") return "Active";
  if (plan === "free") return "Preview";
  return plan || "Preview";
}
