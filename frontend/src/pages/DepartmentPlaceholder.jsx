import { Navigate, useParams } from "react-router-dom";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { PageHeader, LoadingScreen, ErrorScreen, EmptyState, GlassCard } from "@/components/kit";
import { departmentIcon } from "@/lib/departmentIcons";

/** Real department pages — keep in sync with App.js routes / AppLayout DEPT_ROUTE. */
const REAL_DEPARTMENT_PAGES = {
  production: "/app/departments/production",
  procurement: "/app/departments/procurement",
  legal: "/app/departments/legal",
  engineering_maintenance: "/app/departments/engineering_maintenance",
  hr: "/app/departments/hr",
  sales: "/app/sales",
  accounting_finance: "/app/financials",
};

export default function DepartmentPlaceholder() {
  const { deptType } = useParams();
  const { data, loading, error, reload } = useFetch(
    deptType ? `/departments/by-type/${encodeURIComponent(deptType)}` : null,
  );

  if (loading) return <LoadingScreen label="Loading department" />;

  if (error) {
    const status = error?.response?.status;
    if (status === 403) {
      return (
        <ErrorScreen
          label="Access denied"
          message="You are not a member of this department. Ask your CEO to add you."
          onRetry={reload}
        />
      );
    }
    if (status === 404) {
      return (
        <ErrorScreen
          label="Department unavailable"
          message={fetchErrorMessage(error, "This department is not enabled for your company.")}
          onRetry={reload}
        />
      );
    }
    return (
      <ErrorScreen
        label="Could not load department"
        message={fetchErrorMessage(error, "Something went wrong.")}
        onRetry={reload}
      />
    );
  }

  if (!data) return null;

  const realTo = REAL_DEPARTMENT_PAGES[data.type];
  // Dedicated routes take precedence in App.js; this catches any miss and avoids a false "coming soon".
  if (realTo) {
    return <Navigate to={realTo} replace />;
  }

  const Icon = departmentIcon(data.icon);
  const name = data.name || "Department";

  return (
    <div data-testid={`dept-placeholder-${data.type}`}>
      <PageHeader title={name} subtitle="Department workspace" />
      <GlassCard className="p-8">
        <EmptyState
          icon={Icon}
          title={`${name} — coming soon`}
          body={`${name} tools are coming soon. Reach out if there's a specific workflow you want prioritized.`}
        />
      </GlassCard>
    </div>
  );
}
