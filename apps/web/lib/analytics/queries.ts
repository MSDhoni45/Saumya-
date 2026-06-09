"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { AnalyticsOverview } from "./types";

export const analyticsKeys = {
  overview: (businessId: string, days: number) =>
    ["analytics", businessId, "overview", days] as const,
};

export function useAnalyticsOverview(businessId: string, days: number) {
  return useQuery({
    queryKey: analyticsKeys.overview(businessId, days),
    queryFn: () =>
      api.get<AnalyticsOverview>(
        `/analytics/${businessId}/overview?days=${days}`,
      ),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
