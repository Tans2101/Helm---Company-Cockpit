import { useParams } from "react-router-dom";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { PageHeader, LoadingScreen, ErrorScreen, EmptyState, GlassCard } from "@/components/kit";
import { departmentIcon } from "@/lib/departmentIcons";

/** Catalog types that still use this placeholder shell. */
export const PLACEHOLDER_DEPARTMENT_TYPES = [
  "hr",
  "engineering_maintenance",
];

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
