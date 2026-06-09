"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  AiAgent,
  CreateAgentRequest,
  TestRequest,
  TestResponse,
  UpdateAgentRequest,
} from "./types";

export const agentKeys = {
  list: (businessId: string) => ["agents", businessId] as const,
  detail: (businessId: string, agentId: string) => ["agents", businessId, agentId] as const,
};

export function useAgents(businessId: string) {
  return useQuery({
    queryKey: agentKeys.list(businessId),
    queryFn: () => api.get<AiAgent[]>(`/agents/${businessId}`),
  });
}

export function useAgent(businessId: string, agentId: string) {
  return useQuery({
    queryKey: agentKeys.detail(businessId, agentId),
    queryFn: () => api.get<AiAgent>(`/agents/${businessId}/${agentId}`),
    enabled: !!agentId,
  });
}

export function useCreateAgent(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateAgentRequest) =>
      api.post<AiAgent>(`/agents/${businessId}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentKeys.list(businessId) });
    },
  });
}

export function useUpdateAgent(businessId: string, agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateAgentRequest) =>
      api.patch<AiAgent>(`/agents/${businessId}/${agentId}`, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(agentKeys.detail(businessId, agentId), updated);
      queryClient.invalidateQueries({ queryKey: agentKeys.list(businessId) });
    },
  });
}

export function useDeleteAgent(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agentId: string) =>
      api.delete<void>(`/agents/${businessId}/${agentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentKeys.list(businessId) });
    },
  });
}

export function useTestAgent(businessId: string, agentId: string) {
  return useMutation({
    mutationFn: (body: TestRequest) =>
      api.post<TestResponse>(`/agents/${businessId}/${agentId}/test`, body),
  });
}
