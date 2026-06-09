"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { ConversationList } from "@/components/inbox/conversation-list";
import { MessageThread } from "@/components/inbox/message-thread";
import type { UserRole } from "@/lib/auth/rbac";
import { useConversations } from "@/lib/inbox/queries";

/**
 * Master-detail inbox shell.
 *
 * Conversation selection is synced to the URL (`?c=<id>`) so refreshing the
 * page restores the open thread and deep links work across sessions. On narrow
 * viewports the two panes collapse into a single-pane stack: selecting a
 * conversation hides the list and shows the thread, and the thread header's
 * back button reverses that.
 */
export function InboxView({
  businessId,
  currentUser,
}: {
  businessId: string;
  currentUser: { id: string; role: UserRole };
}) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const selectedConversationId = searchParams.get("c");

  const setSelectedConversationId = useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id) {
        params.set("c", id);
      } else {
        params.delete("c");
      }
      router.push(`/inbox?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const conversationsQuery = useConversations(businessId);
  const conversations = conversationsQuery.data ?? [];
  const selectedConversation =
    conversations.find((conversation) => conversation.id === selectedConversationId) ?? null;

  return (
    <div className="flex h-full">
      <ConversationList
        conversations={conversations}
        isLoading={conversationsQuery.isLoading}
        isError={conversationsQuery.isError}
        onRetry={() => conversationsQuery.refetch()}
        selectedConversationId={selectedConversationId}
        onSelectConversation={setSelectedConversationId}
        currentUserId={currentUser.id}
        className={selectedConversationId ? "hidden md:flex" : "flex"}
      />
      <MessageThread
        businessId={businessId}
        conversation={selectedConversation}
        currentUser={currentUser}
        onBack={() => setSelectedConversationId(null)}
        className={selectedConversationId ? "flex" : "hidden md:flex"}
      />
    </div>
  );
}
