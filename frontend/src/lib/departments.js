/**
 * @deprecated Legacy free-text People/Members labels (Engineering, Product, Sales…).
 * These are NOT the access-control department system (`departments` /
 * `department_members`: Procurement, Production, Accounting & Finance, Sales,
 * Legal, HR, Engineering & Maintenance). Kept only so any missed callers still
 * import without crashing. Do not use for new UI — assign access via Team &
 * Access department membership. A follow-up can delete this file once unused.
 */
export const DEFAULT_DEPARTMENTS = [
  "Engineering",
  "Product",
  "Sales",
  "Marketing",
  "Finance",
  "Operations",
  "Support",
  "HR",
  "Growth",
  "General",
];

/** @deprecated Custom-option sentinel for the retired People department dropdown. */
export const CUSTOM_DEPT = "__custom__";

export function formatDepartmentNames(personOrNames) {
  const names = Array.isArray(personOrNames)
    ? personOrNames
    : (personOrNames?.departments || []);
  const cleaned = names.map((n) => String(n || "").trim()).filter(Boolean);
  return cleaned.length ? cleaned.join(", ") : "Unassigned";
}
