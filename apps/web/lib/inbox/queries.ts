"use client";

/**
 * Data layer for the WhatsApp Inbox.
 *
 * The backend has no WebSocket/pub-sub channel (only Celery+Redis task queues
 * for AI processing — see app/workers), so "real-time" here means polling via
 * TanStack Query's `refetchInterval`. By default that pauses while the tab is
 * hidden, which is what we want — no need to wire `visibilitychange` by hand.
 *
 * Every hook here is intentionally a thin wrapper around `api.*` + the shared
 * query-key factory, so a future push-based transport (WebSocket/SSE) can
 * replace the `queryFn`/polling without touching any component.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  Conversation,
  ConversationUpdatePayload,
  Message,
  SendMessageResult,
} from "@/lib/inbox/types";

export const inboxKeys = {
  conversations: (businessId: string) => ["inbox", businessId, "conversations"] as const,
  messages: (businessId: string, conversationId: string) =>
    ["inbox", businessId, "conversations", conversationId, "messages"] as const,
};

const CONVERSATIONS_POLL_MS = 20_000;
const MESSAGES_POLL_MS = 4_000;

export function useConversations(businessId: string) {
  return useQuery({
    queryKey: inboxKeys.conversations(businessId),
    queryFn: () => api.get<Conversation[]>(`/whatsapp/${businessId}/conversations`),
    refetchInterval: CONVERSATIONS_POLL_MS,
  });
}

export function useConversationMessages(businessId: string, conversationId: string | null) {
  return useQuery({
    queryKey: inboxKeys.messages(businessId, conversationId ?? "_none"),
    queryFn: () => api.get<Message[]>(`/whatsapp/${businessId}/conversations/${conversationId}/messages`),
    enabled: conversationId !== null,
    refetchInterval: MESSAGES_POLL_MS,
  });
}

interface SendMessageVariables {
  conversation: Conversation;
  text: string;
}

/**
 * Sends a text reply and inserts an optimistic bubble immediately so the
 * thread never feels like it's waiting on the network for the agent's own
 * message. Rolls back on failure (the bubble flips to a "failed" state via
 * cache restoration, then disappears once the user retries or the cache is
 * invalidated).
 */
export function useSendMessage(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ conversation, text }: SendMessageVariables) =>
      api.post<SendMessageResult>(`/whatsapp/${businessId}/accounts/${conversation.whatsapp_account_id}/send`, {
        to: conversation.contact_phone,
        message_type: "text",
        text,
      }),
    onMutate: async ({ conversation, text }) => {
      const key = inboxKeys.messages(businessId, conversation.id);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Message[]>(key);

      const optimisticMessage: Message = {
        id: `optimistic-${crypto.randomUUID()}`,
        conversation_id: conversation.id,
        direction: "outbound",
        sender_type: "agent",
        message_type: "text",
        content: text,
        media_url: null,
        status: "queued",
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData<Message[]>(key, (old) => [...(old ?? []), optimisticMessage]);
      return { previous };
    },
    onError: (_error, { conversation }, context) => {
      queryClient.setQueryData(inboxKeys.messages(businessId, conversation.id), context?.previous);
    },
    onSettled: (_data, _error, { conversation }) => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.messages(businessId, conversation.id) });
      queryClient.invalidateQueries({ queryKey: inboxKeys.conversations(businessId) });
    },
  });
}

interface UpdateConversationVariables {
  conversationId: string;
  payload: ConversationUpdatePayload;
}

/**
 * Backs takeover / hand-back / reassignment. Optimistically patches the
 * conversation inside the cached list (the selected conversation is derived
 * from that same list, so this is the single source of truth to update).
 */
export function useUpdateConversation(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ conversationId, payload }: UpdateConversationVariables) =>
      api.patch<Conversation>(`/whatsapp/${businessId}/conversations/${conversationId}`, payload),
    onMutate: async ({ conversationId, payload }) => {
      const key = inboxKeys.conversations(businessId);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Conversation[]>(key);

      queryClient.setQueryData<Conversation[]>(key, (old) =>
        old?.map((conversation) => (conversation.id === conversationId ? { ...conversation, ...payload } : conversation)),
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(inboxKeys.conversations(businessId), context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.conversations(businessId) });
    },
  });
}
