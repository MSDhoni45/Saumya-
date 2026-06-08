"use client";

import { useState } from "react";

import { ConversationList } from "@/components/inbox/conversation-list";
import { MessageThread } from "@/components/inbox/message-thread";
import type { UserRole } from "@/lib/auth/rbac";
import { useConversations } from "@/lib/inbox/queries";

/**
 * Master-detail inbox shell. Selection lives in local state (not the URL) —
 * search/filters are scoped to the list pane, and a deep-link contract isn't
 * needed yet. On narrow viewports the two panes collapse into a single-pane
 * stack: selecting a conversation hides the list and shows the thread, and
 * the thread header's back button reverses that.
 */
export function InboxView({
  businessId,
  currentUser,
}: {
  businessId: string;
  currentUser: { id: string; role: UserRole };
}) {
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);

  const conversationsQuery = useConversations(businessId);
  const conversations = conversationsQuery.data ?? [];
  const selectedConversation = conversations.find((conversation) => conversation.id === selectedConversationId) ?? null;

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
