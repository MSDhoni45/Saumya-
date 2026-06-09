"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  AcceptInviteRequest,
  AcceptInviteResponse,
  InviteDetails,
  InviteRequest,
  TeamInvite,
  TeamMember,
} from "./types";

export const teamKeys = {
  members: (businessId: string) => ["team", businessId, "members"] as const,
  invites: (businessId: string) => ["team", businessId, "invites"] as const,
  invite: (token: string) => ["invite", token] as const,
};

export function useMembers(businessId: string) {
  return useQuery({
    queryKey: teamKeys.members(businessId),
    queryFn: () => api.get<TeamMember[]>(`/team/${businessId}/members`),
  });
}

export function useInvites(businessId: string) {
  return useQuery({
    queryKey: teamKeys.invites(businessId),
    queryFn: () => api.get<TeamInvite[]>(`/team/${businessId}/invites`),
  });
}

export function useCreateInvite(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: InviteRequest) =>
      api.post<TeamInvite>(`/team/${businessId}/invites`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamKeys.invites(businessId) });
    },
  });
}

export function useRevokeInvite(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) =>
      api.delete<void>(`/team/${businessId}/invites/${inviteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamKeys.invites(businessId) });
    },
  });
}

export function useRemoveMember(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      api.delete<void>(`/team/${businessId}/members/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamKeys.members(businessId) });
    },
  });
}

export function useChangeRole(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.patch<TeamMember>(`/team/${businessId}/members/${userId}`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamKeys.members(businessId) });
    },
  });
}

export function useInviteDetails(token: string) {
  return useQuery({
    queryKey: teamKeys.invite(token),
    queryFn: () => api.get<InviteDetails>(`/invites/${token}`),
    enabled: !!token,
    retry: false,
  });
}

export function useAcceptInvite(token: string) {
  return useMutation({
    mutationFn: (body: AcceptInviteRequest) =>
      api.post<AcceptInviteResponse>(`/invites/${token}/accept`, body),
  });
}
