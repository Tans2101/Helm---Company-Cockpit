/** Paths for enabled department pages — keep in sync with App.js / AppLayout. */
export const DEPARTMENT_ROUTES = {
  sales: "/app/sales",
  accounting_finance: "/app/financials",
  production: "/app/departments/production",
  procurement: "/app/departments/procurement",
  legal: "/app/departments/legal",
  engineering_maintenance: "/app/departments/engineering_maintenance",
  hr: "/app/departments/hr",
};

export function departmentPath(type) {
  return DEPARTMENT_ROUTES[type] || `/app/departments/${type}`;
}

/** Account settings anchor for the manage-departments section. */
export const MANAGE_DEPARTMENTS_HREF = "/app/settings#manage-departments";
