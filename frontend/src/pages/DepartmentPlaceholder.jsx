import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { api } from "@/lib/api";
import { PageHeader, ErrorScreen, EmptyState, GlassCard, PageHeaderSkeleton, SkeletonCardList } from "@/components/kit";
import { departmentIcon } from "@/lib/departmentIcons";
import { departmentPath, DEPARTMENT_ROUTES, MANAGE_DEPARTMENTS_HREF } from "@/lib/departmentRoutes";

export default function DepartmentPlaceholder() {
  const { deptType } = useParams();
  const { data, loading, error, reload } = useFetch(
    deptType ? `/departments/by-type/${encodeURIComponent(deptType)}` : null,
  );
  // Catalog flags (can_manage / name) for the not-enabled case
  const { data: catalog, reload: reloadCatalog } = useFetch("/departments");
  const [enabling, setEnabling] = useState(false);

  if (loading) {
    return (
      <div>
        <PageHeaderSkeleton />
        <SkeletonCardList count={2} />
      </div>
    );
  }

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
      const entry = (catalog?.departments || []).find((d) => d.type === deptType);
      const name = entry?.name || deptType?.replace(/_/g, " ") || "Department";
      const canManage = Boolean(catalog?.can_manage || catalog?.is_ceo);
      const Icon = departmentIcon(entry?.icon);

      const enableHere = async () => {
        if (!deptType) return;
        setEnabling(true);
        try {
          await api.post("/departments", { type: deptType });
          toast.success(`${name} enabled`);
          // Full assign so AppLayout refetches /departments and the nav updates.
          window.location.assign(departmentPath(deptType));
        } catch (e) {
          toast.error(e?.response?.data?.detail || "Could not enable department");
          setEnabling(false);
          reloadCatalog();
        }
      };

      return (
        <div data-testid={`dept-not-enabled-${deptType || "unknown"}`}>
          <PageHeader title={name} subtitle="Not enabled for this company" />
          <GlassCard className="p-8">
            <EmptyState
              icon={Icon}
              title={`${name} isn’t enabled yet`}
              body={
                canManage
                  ? "Enable this department to open its tools. Any CEO can turn on any catalog department. Industry choice doesn’t restrict this."
                  : "This department isn’t enabled for your company. Ask your CEO to enable it from Account settings → Manage departments."
              }
              action={(
                <div className="flex flex-wrap items-center justify-center gap-3">
                  {canManage && (
                    <button
                      type="button"
                      data-testid="enable-department-here-btn"
                      disabled={enabling}
                      onClick={enableHere}
                      className="rounded-md bg-helm-gold text-helm-navy font-medium text-sm px-4 py-2.5 hover:bg-helm-gold-hover disabled:opacity-60"
                    >
                      {enabling ? "Enabling…" : `Enable ${name}`}
                    </button>
                  )}
                  <Link
                    to={MANAGE_DEPARTMENTS_HREF}
                    data-testid="manage-departments-link"
                    className="rounded-md border border-helm-line text-helm-fg text-sm px-4 py-2.5 hover:border-helm-gold/35"
                  >
                    Manage departments
                  </Link>
                  <button
                    type="button"
                    onClick={reload}
                    className="text-sm text-helm-muted hover:text-helm-fg"
                  >
                    Try again
                  </button>
                </div>
              )}
            />
          </GlassCard>
        </div>
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

  const realTo = DEPARTMENT_ROUTES[data.type];
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
          title={`${name} coming soon`}
          body={`${name} tools are coming soon. Reach out if there's a specific workflow you want prioritized.`}
        />
      </GlassCard>
    </div>
  );
}
