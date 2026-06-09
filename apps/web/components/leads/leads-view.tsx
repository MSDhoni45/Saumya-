"use client";

import { useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { LeadDetail } from "@/components/leads/lead-detail";
import { LeadList } from "@/components/leads/lead-list";
import type { LeadFilters, LeadStage } from "@/lib/leads/types";

const PAGE_SIZE = 20;

function parseFilters(params: URLSearchParams): LeadFilters {
  const stageParam = params.get("stage") ?? "";
  const sourceParam = params.get("source") ?? "";

  const stage = new Set<LeadStage>(
    stageParam
      ? (stageParam.split(",").filter(Boolean) as LeadStage[])
      : [],
  );
  const source = new Set<string>(
    sourceParam ? sourceParam.split(",").filter(Boolean) : [],
  );

  const assignedRaw = params.get("assigned") ?? "all";
  const assigned =
    assignedRaw === "me" || assignedRaw === "unassigned" ? assignedRaw : "all";

  const sortRaw = params.get("sort") ?? "updated_desc";
  const sort =
    sortRaw === "created_asc" || sortRaw === "stage_asc"
      ? (sortRaw as LeadFilters["sort"])
      : "updated_desc";

  return {
    q: params.get("q") ?? "",
    stage,
    source,
    assigned,
    sort,
    page: Math.max(1, Number(params.get("page") ?? "1")),
  };
}

function filtersToParams(filters: LeadFilters): Record<string, string> {
  const out: Record<string, string> = {};
  if (filters.q) out.q = filters.q;
  if (filters.stage.size > 0) out.stage = Array.from(filters.stage).join(",");
  if (filters.source.size > 0) out.source = Array.from(filters.source).join(",");
  if (filters.assigned !== "all") out.assigned = filters.assigned;
  if (filters.sort !== "updated_desc") out.sort = filters.sort;
  if (filters.page > 1) out.page = String(filters.page);
  return out;
}

export function LeadsView({
  businessId,
  currentUserId,
}: {
  businessId: string;
  currentUserId: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedLeadId = searchParams.get("lead");
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);

  const pushParams = useCallback(
    (next: URLSearchParams) => {
      router.push(`/leads?${next.toString()}`, { scroll: false });
    },
    [router],
  );

  const handleSelectLead = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("lead", id);
      pushParams(params);
    },
    [searchParams, pushParams],
  );

  const handleBack = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("lead");
    pushParams(params);
  }, [searchParams, pushParams]);

  const handleFilterChange = useCallback(
    (patch: Partial<LeadFilters>) => {
      const merged: LeadFilters = { ...filters, ...patch };
      const params = new URLSearchParams(filtersToParams(merged));
      if (selectedLeadId) params.set("lead", selectedLeadId);
      pushParams(params);
    },
    [filters, selectedLeadId, pushParams],
  );

  return (
    <div className="flex h-full">
      <LeadList
        businessId={businessId}
        filters={filters}
        selectedLeadId={selectedLeadId}
        onSelectLead={handleSelectLead}
        onFilterChange={handleFilterChange}
        className={selectedLeadId ? "hidden md:flex" : "flex"}
      />
      <LeadDetail
        businessId={businessId}
        leadId={selectedLeadId}
        currentUserId={currentUserId}
        onBack={handleBack}
        className={selectedLeadId ? "flex" : "hidden md:flex"}
      />
    </div>
  );
}
