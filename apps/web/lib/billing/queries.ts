"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  CancelResponse,
  CheckoutRequest,
  CheckoutResponse,
  Plan,
  Subscription,
  Usage,
} from "@/lib/billing/types";

export const billingKeys = {
  plans: (businessId: string) => ["billing", businessId, "plans"] as const,
  subscription: (businessId: string) => ["billing", businessId, "subscription"] as const,
  usage: (businessId: string) => ["billing", businessId, "usage"] as const,
};

export function usePlans(businessId: string) {
  return useQuery({
    queryKey: billingKeys.plans(businessId),
    queryFn: () => api.get<Plan[]>(`/billing/${businessId}/plans`),
  });
}

export function useSubscription(businessId: string) {
  return useQuery({
    queryKey: billingKeys.subscription(businessId),
    queryFn: () => api.get<Subscription>(`/billing/${businessId}/subscription`),
  });
}

export function useUsage(businessId: string) {
  return useQuery({
    queryKey: billingKeys.usage(businessId),
    queryFn: () => api.get<Usage>(`/billing/${businessId}/usage`),
    refetchInterval: 60_000, // refresh every minute
  });
}

export function useCheckout(businessId: string) {
  return useMutation({
    mutationFn: (body: CheckoutRequest) =>
      api.post<CheckoutResponse>(`/billing/${businessId}/checkout`, body),
  });
}

export function useChangePlan(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (plan: string) =>
      api.post<Subscription>(`/billing/${businessId}/change-plan`, { plan }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing", businessId] });
    },
  });
}

export function useCancelSubscription(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CancelResponse>(`/billing/${businessId}/cancel`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing", businessId] });
    },
  });
}

export function useReactivateSubscription(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Subscription>(`/billing/${businessId}/reactivate`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing", businessId] });
    },
  });
}
