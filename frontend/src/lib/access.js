/** Access packs mirror backend PACK_* maps in server.py */

export const PACK_LABELS = {
  owner: "Owner",
  exec: "Executive",
  finance: "Finance",
  hr: "HR",
  sales: "Sales",
  ops: "Ops",
  member: "Member",
};

/** Empty array = all modules visible */
export const PACK_MODULES = {
  owner: [],
  exec: [],
  member: [],
  finance: ["briefing", "financials", "tasks", "ask"],
  hr: ["briefing", "people", "team", "tasks", "ask"],
  sales: ["briefing", "telemetry", "tasks", "ask"],
  ops: ["briefing", "telemetry", "tasks", "team", "ask"],
};

export const PACK_HOME = {
  owner: "/app",
  exec: "/app",
  member: "/app",
  finance: "/app/financials",
  hr: "/app/people",
  sales: "/app/telemetry",
  ops: "/app/tasks",
};

export function normalizeRole(role) {
  return PACK_LABELS[role] ? role : "member";
}

export function modulesFor(role) {
  return PACK_MODULES[normalizeRole(role)] || [];
}

export function canAccessModule(role, moduleId) {
  const mods = modulesFor(role);
  return mods.length === 0 || mods.includes(moduleId);
}

export function homeFor(user) {
  if (user?.home) return user.home;
  return PACK_HOME[normalizeRole(user?.role)] || "/app";
}

export function hasPerm(user, action) {
  if (Array.isArray(user?.perms)) return user.perms.includes(action);
  if (user?.role === "owner") return true;
  return false;
}
