import { useState } from "react";
import { useParams } from "react-router-dom";
import { useFetch, fetchErrorMessage } from "@/hooks/useFetch";
import { PageHeader, LoadingScreen, ErrorScreen, EmptyState, GlassCard } from "@/components/kit";
import { Building2 } from "lucide-react";

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

  return (
    <div>
      <PageHeader title={data.name} subtitle="Department workspace" />
      <GlassCard className="p-8">
        <EmptyState
          icon={Building2}
          title={`${data.name} — coming soon`}
          body="Department tools will land here in a later update. Membership and access already work from Settings."
        />
      </GlassCard>
    </div>
  );
}
