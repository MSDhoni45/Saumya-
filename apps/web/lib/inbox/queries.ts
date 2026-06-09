"use client";

/**
 * Data layer for the WhatsApp Inbox.
 *
 * Transport strategy
 * ------------------
 * Active message threads use a Server-Sent Events (SSE) stream
 * (`useMessageStream`) for near-instant delivery. The REST polling hooks
 * (`useConversationMessages`, `useConversations`) run in parallel as the
 * authoritative state and as fallback when SSE is unavailable.
 *
 * Splitting SSE from polling means we never show stale data (polling always
 * reconciles) while still getting low-latency push updates (SSE injects
 * messages into the cache without waiting for the next poll cycle).
 */

import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type {
  ConnectWhatsAppPayload,
  Conversation,
  ConversationUpdatePayload,
  Message,
  SendMessageResult,
  WhatsAppAccount,
} from "@/lib/inbox/types";

export const inboxKeys = {
  conversations: (businessId: string) => ["inbox", businessId, "conversations"] as const,
  messages: (businessId: string, conversationId: string) =>
    ["inbox", businessId, "conversations", conversationId, "messages"] as const,
  accounts: (businessId: string) => ["inbox", businessId, "accounts"] as const,
};

const CONVERSATIONS_POLL_MS = 20_000;
const MESSAGES_POLL_MS = 4_000;

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

export function useConversations(businessId: string) {
  return useQuery({
    queryKey: inboxKeys.conversations(businessId),
    queryFn: () => api.get<Conversation[]>(`/whatsapp/${businessId}/conversations`),
    refetchInterval: CONVERSATIONS_POLL_MS,
  });
}

// ---------------------------------------------------------------------------
// Messages — REST polling (authoritative source)
// ---------------------------------------------------------------------------

export function useConversationMessages(businessId: string, conversationId: string | null) {
  return useQuery({
    queryKey: inboxKeys.messages(businessId, conversationId ?? "_none"),
    queryFn: () => api.get<Message[]>(`/whatsapp/${businessId}/conversations/${conversationId}/messages`),
    enabled: conversationId !== null,
    refetchInterval: MESSAGES_POLL_MS,
  });
}

// ---------------------------------------------------------------------------
// SSE stream — push new messages into the cache without a full refetch
// ---------------------------------------------------------------------------

/**
 * Opens a Server-Sent Events connection to the backend's `/stream` endpoint
 * for a specific conversation. Each `data:` event carries a JSON-encoded
 * Message object that is immediately appended to the TanStack Query cache.
 *
 * The hook is additive-only (it never removes messages) so it can safely
 * co-exist with the polling hook above — duplicates are deduplicated by `id`.
 * On error or disconnect the browser's native EventSource auto-reconnects with
 * exponential backoff; we also invalidate the REST query on reconnect to catch
 * any messages missed during the gap.
 */
export function useMessageStream(businessId: string, conversationId: string | null) {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!conversationId) return;

    const key = inboxKeys.messages(businessId, conversationId);
    const url = `/backend/api/v1/whatsapp/${businessId}/conversations/${conversationId}/stream`;

    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;

    es.addEventListener("connected", () => {
      // Re-fetch once on (re)connect to catch any messages that arrived while
      // the connection was being established or during a reconnect gap.
      queryClient.invalidateQueries({ queryKey: key });
    });

    es.onmessage = (event: MessageEvent<string>) => {
      try {
        const message: Message = JSON.parse(event.data);
        queryClient.setQueryData<Message[]>(key, (old) => {
          if (!old) return old;
          // Deduplicate: SSE may deliver a message the REST poll already fetched.
          if (old.some((m) => m.id === message.id)) return old;
          return [...old, message];
        });

        // Also invalidate the conversation list so `last_message_content` /
        // `last_message_at` refresh.
        queryClient.invalidateQueries({
          queryKey: inboxKeys.conversations(businessId),
          refetchType: "active",
        });
      } catch {
        // Malformed SSE payload — ignore, the polling layer will catch up.
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [businessId, conversationId, queryClient]);
}

// ---------------------------------------------------------------------------
// Send message (with optimistic UI)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Update conversation (takeover / hand-back / close / reopen)
// ---------------------------------------------------------------------------

interface UpdateConversationVariables {
  conversationId: string;
  payload: ConversationUpdatePayload;
}

/**
 * Backs takeover / hand-back / close / reopen. Optimistically patches the
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

// ---------------------------------------------------------------------------
// WhatsApp accounts (for settings page)
// ---------------------------------------------------------------------------

export function useWhatsAppAccounts(businessId: string) {
  return useQuery({
    queryKey: inboxKeys.accounts(businessId),
    queryFn: () => api.get<WhatsAppAccount[]>(`/whatsapp/${businessId}/accounts`),
  });
}

export function useConnectWhatsApp(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConnectWhatsAppPayload) =>
      api.post<WhatsAppAccount>(`/whatsapp/${businessId}/connect`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.accounts(businessId) });
    },
  });
}

export function useDisconnectWhatsApp(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) =>
      api.post<WhatsAppAccount>(`/whatsapp/${businessId}/accounts/${accountId}/disconnect`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.accounts(businessId) });
    },
  });
}
