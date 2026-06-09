"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  Lead,
  LeadFilters,
  LeadNote,
  LeadTimeline,
  LeadUpdatePayload,
  PaginatedLeads,
} from "@/lib/leads/types";

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const leadKeys = {
  list: (businessId: string, filters: Partial<LeadFilters>) =>
    ["leads", businessId, "list", filters] as const,
  detail: (businessId: string, leadId: string) =>
    ["leads", businessId, "detail", leadId] as const,
  timeline: (businessId: string, leadId: string) =>
    ["leads", businessId, "timeline", leadId] as const,
};

// ---------------------------------------------------------------------------
// List with filters + pagination
// ---------------------------------------------------------------------------

function buildListPath(businessId: string, filters: Partial<LeadFilters>): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.stage?.size) params.set("stage", [...filters.stage].join(","));
  if (filters.source?.size) params.set("source", [...filters.source].join(","));
  if (filters.assigned && filters.assigned !== "all") params.set("assigned", filters.assigned);
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.page && filters.page > 1) params.set("page", String(filters.page));
  const qs = params.toString();
  return `/leads/${businessId}${qs ? `?${qs}` : ""}`;
}

export function useLeads(businessId: string, filters: Partial<LeadFilters>) {
  return useQuery({
    queryKey: leadKeys.list(businessId, filters),
    queryFn: () => api.get<PaginatedLeads>(buildListPath(businessId, filters)),
    placeholderData: (previous) => previous,
  });
}

// ---------------------------------------------------------------------------
// Single lead
// ---------------------------------------------------------------------------

export function useLead(businessId: string, leadId: string | null) {
  return useQuery({
    queryKey: leadKeys.detail(businessId, leadId ?? "_none"),
    queryFn: () => api.get<Lead>(`/leads/${businessId}/${leadId}`),
    enabled: leadId !== null,
  });
}

// ---------------------------------------------------------------------------
// Timeline
// ---------------------------------------------------------------------------

export function useLeadTimeline(businessId: string, leadId: string | null) {
  return useQuery({
    queryKey: leadKeys.timeline(businessId, leadId ?? "_none"),
    queryFn: () => api.get<LeadTimeline>(`/leads/${businessId}/${leadId}/timeline`),
    enabled: leadId !== null,
  });
}

// ---------------------------------------------------------------------------
// Update lead (stage / fields / assignment) — optimistic
// ---------------------------------------------------------------------------

export function useUpdateLead(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ leadId, payload, actorId }: { leadId: string; payload: LeadUpdatePayload; actorId?: string }) => {
      const qs = actorId ? `?actor_id=${actorId}` : "";
      return api.patch<Lead>(`/leads/${businessId}/${leadId}${qs}`, payload);
    },
    onMutate: async ({ leadId, payload }) => {
      const detailKey = leadKeys.detail(businessId, leadId);
      await queryClient.cancelQueries({ queryKey: detailKey });
      const previous = queryClient.getQueryData<Lead>(detailKey);
      if (previous) {
        queryClient.setQueryData<Lead>(detailKey, { ...previous, ...payload });
      }
      return { previous, leadId };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(leadKeys.detail(businessId, context.leadId), context.previous);
      }
    },
    onSettled: (_data, _error, { leadId }) => {
      queryClient.invalidateQueries({ queryKey: leadKeys.detail(businessId, leadId) });
      queryClient.invalidateQueries({ queryKey: ["leads", businessId, "list"] });
      queryClient.invalidateQueries({ queryKey: leadKeys.timeline(businessId, leadId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Add note — optimistic insert into timeline
// ---------------------------------------------------------------------------

export function useAddNote(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ leadId, content, authorId }: { leadId: string; content: string; authorId?: string }) => {
      const qs = authorId ? `?author_id=${authorId}` : "";
      return api.post<LeadNote>(`/leads/${businessId}/${leadId}/notes${qs}`, { content });
    },
    onSuccess: (_data, { leadId }) => {
      queryClient.invalidateQueries({ queryKey: leadKeys.timeline(businessId, leadId) });
      queryClient.invalidateQueries({ queryKey: ["leads", businessId, "list"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Delete note
// ---------------------------------------------------------------------------

export function useDeleteNote(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ leadId, noteId, actorId }: { leadId: string; noteId: string; actorId?: string }) => {
      const qs = actorId ? `?actor_id=${actorId}` : "";
      return api.delete<void>(`/leads/${businessId}/${leadId}/notes/${noteId}${qs}`);
    },
    onSuccess: (_data, { leadId }) => {
      queryClient.invalidateQueries({ queryKey: leadKeys.timeline(businessId, leadId) });
    },
  });
}
