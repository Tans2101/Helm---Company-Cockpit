import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** Shared key so AppLayout, Briefing, and AccountSettings dedupe /company. */
export const COMPANY_QUERY_KEY = ["company"];

export function useCompanyQuery() {
  const query = useQuery({
    queryKey: COMPANY_QUERY_KEY,
    queryFn: async () => {
      const { data } = await api.get("/company");
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

export function useInvalidateCompany() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: COMPANY_QUERY_KEY });
}
