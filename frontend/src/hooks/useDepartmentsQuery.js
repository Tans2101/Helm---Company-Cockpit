import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** Shared key so SidebarContent and QuickNavPalette (and settings) dedupe /departments. */
export const DEPARTMENTS_QUERY_KEY = ["departments"];

export function useDepartmentsQuery() {
  const query = useQuery({
    queryKey: DEPARTMENTS_QUERY_KEY,
    queryFn: async () => {
      const { data } = await api.get("/departments");
      return data;
    },
  });
  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error ?? null,
    reload: () => query.refetch(),
  };
}

export function useInvalidateDepartments() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: DEPARTMENTS_QUERY_KEY });
}
