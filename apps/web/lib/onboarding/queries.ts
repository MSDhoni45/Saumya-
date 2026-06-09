"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  AddDocumentPayload,
  AgentCreatePayload,
  AgentDetail,
  AgentTestPayload,
  AgentTestResult,
  BusinessDetail,
  BusinessUpdatePayload,
  CreateKbPayload,
  KbDocument,
  KnowledgeBase,
} from "@/lib/onboarding/types";

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const onboardingKeys = {
  business: (id: string) => ["onboarding", "business", id] as const,
  kbs: (businessId: string) => ["onboarding", "kbs", businessId] as const,
  agents: (businessId: string) => ["onboarding", "agents", businessId] as const,
};

// ---------------------------------------------------------------------------
// Business
// ---------------------------------------------------------------------------

export function useBusiness(businessId: string) {
  return useQuery({
    queryKey: onboardingKeys.business(businessId),
    queryFn: () => api.get<BusinessDetail>(`/business/${businessId}`),
  });
}

export function useUpdateBusiness(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BusinessUpdatePayload) =>
      api.patch<BusinessDetail>(`/business/${businessId}`, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.business(businessId), data);
    },
  });
}

// ---------------------------------------------------------------------------
// Knowledge base
// ---------------------------------------------------------------------------

export function useKnowledgeBases(businessId: string) {
  return useQuery({
    queryKey: onboardingKeys.kbs(businessId),
    queryFn: () => api.get<KnowledgeBase[]>(`/knowledge/${businessId}`),
  });
}

export function useCreateKb(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateKbPayload) =>
      api.post<KnowledgeBase>(`/knowledge/${businessId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: onboardingKeys.kbs(businessId) }),
  });
}

export function useAddDocument(businessId: string, kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AddDocumentPayload) =>
      api.post<KbDocument>(`/knowledge/${businessId}/${kbId}/documents`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: onboardingKeys.kbs(businessId) }),
  });
}

export function useDeleteDocument(businessId: string, kbId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) =>
      api.delete(`/knowledge/${businessId}/${kbId}/documents/${docId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: onboardingKeys.kbs(businessId) }),
  });
}

// ---------------------------------------------------------------------------
// AI Agent
// ---------------------------------------------------------------------------

export function useAgents(businessId: string) {
  return useQuery({
    queryKey: onboardingKeys.agents(businessId),
    queryFn: () => api.get<AgentDetail[]>(`/agents/${businessId}`),
  });
}

export function useCreateAgent(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AgentCreatePayload) =>
      api.post<AgentDetail>(`/agents/${businessId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: onboardingKeys.agents(businessId) }),
  });
}

export function useUpdateAgent(businessId: string, agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<AgentCreatePayload>) =>
      api.patch<AgentDetail>(`/agents/${businessId}/${agentId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: onboardingKeys.agents(businessId) }),
  });
}

export function useTestAgent(businessId: string, agentId: string) {
  return useMutation({
    mutationFn: (payload: AgentTestPayload) =>
      api.post<AgentTestResult>(`/agents/${businessId}/${agentId}/test`, payload),
  });
}
