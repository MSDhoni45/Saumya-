"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  PaginatedXOutreach,
  PaginatedXPosts,
  XAccount,
  XAnalytics,
  XLeadSearch,
  XOutreach,
  XPost,
} from "@/lib/x/types";

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

export function useXAccounts(businessId: string) {
  return useQuery({
    queryKey: ["x", businessId, "accounts"],
    queryFn: () => api.get<XAccount[]>(`/x/${businessId}/accounts`),
  });
}

export function useXAuthorizeUrl(businessId: string) {
  return useMutation({
    mutationFn: () =>
      api.get<{ url: string; state: string }>(`/x/${businessId}/accounts/oauth/authorize`),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
  });
}

export function useDisconnectXAccount(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) =>
      api.delete<void>(`/x/${businessId}/accounts/${accountId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "accounts"] }),
  });
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export function useXAnalytics(businessId: string) {
  return useQuery({
    queryKey: ["x", businessId, "analytics"],
    queryFn: () => api.get<XAnalytics>(`/x/${businessId}/analytics`),
  });
}

// ---------------------------------------------------------------------------
// Posts
// ---------------------------------------------------------------------------

export function useXPosts(businessId: string, page = 1, status?: string) {
  return useQuery({
    queryKey: ["x", businessId, "posts", page, status],
    queryFn: () => {
      const qs = new URLSearchParams({ page: String(page) });
      if (status) qs.set("status", status);
      return api.get<PaginatedXPosts>(`/x/${businessId}/posts?${qs}`);
    },
    placeholderData: (prev) => prev,
  });
}

export function useCreateXPost(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      x_account_id: string;
      content: string;
      scheduled_at?: string;
    }) => api.post<XPost>(`/x/${businessId}/posts`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "posts"] }),
  });
}

export function usePublishXPost(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (postId: string) =>
      api.post<XPost>(`/x/${businessId}/posts/${postId}/publish`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "posts"] }),
  });
}

export function useDeleteXPost(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (postId: string) =>
      api.delete<void>(`/x/${businessId}/posts/${postId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "posts"] }),
  });
}

// ---------------------------------------------------------------------------
// Lead searches
// ---------------------------------------------------------------------------

export function useXSearches(businessId: string) {
  return useQuery({
    queryKey: ["x", businessId, "searches"],
    queryFn: () => api.get<XLeadSearch[]>(`/x/${businessId}/searches`),
  });
}

export function useCreateXSearch(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      keywords: string[];
      exclude_keywords: string[];
      min_followers: number;
      language: string;
      auto_dm_enabled: boolean;
      auto_dm_threshold: number;
    }) => api.post<XLeadSearch>(`/x/${businessId}/searches`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "searches"] }),
  });
}

export function useRunXSearch(businessId: string) {
  return useMutation({
    mutationFn: (searchId: string) =>
      api.post<{ queued: boolean }>(`/x/${businessId}/searches/${searchId}/run`),
  });
}

export function useDeleteXSearch(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (searchId: string) =>
      api.delete<void>(`/x/${businessId}/searches/${searchId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "searches"] }),
  });
}

// ---------------------------------------------------------------------------
// Outreach
// ---------------------------------------------------------------------------

export function useXOutreach(
  businessId: string,
  opts: { page?: number; status?: string; min_score?: number },
) {
  return useQuery({
    queryKey: ["x", businessId, "outreach", opts],
    queryFn: () => {
      const qs = new URLSearchParams({ page: String(opts.page ?? 1) });
      if (opts.status) qs.set("status", opts.status);
      if (opts.min_score !== undefined) qs.set("min_score", String(opts.min_score));
      return api.get<PaginatedXOutreach>(`/x/${businessId}/outreach?${qs}`);
    },
    placeholderData: (prev) => prev,
  });
}

export function useSendXDm(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ outreachId, accountId }: { outreachId: string; accountId: string }) =>
      api.post<XOutreach>(`/x/${businessId}/outreach/${outreachId}/send-dm`, {
        account_id: accountId,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "outreach"] }),
  });
}

export function useSendXReply(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ outreachId, accountId }: { outreachId: string; accountId: string }) =>
      api.post<XOutreach>(
        `/x/${businessId}/outreach/${outreachId}/send?account_id=${accountId}`,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "outreach"] }),
  });
}

export function useUpdateXOutreach(businessId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      outreachId,
      payload,
    }: {
      outreachId: string;
      payload: { status?: string; outreach_message?: string };
    }) => api.patch<XOutreach>(`/x/${businessId}/outreach/${outreachId}`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["x", businessId, "outreach"] }),
  });
}
