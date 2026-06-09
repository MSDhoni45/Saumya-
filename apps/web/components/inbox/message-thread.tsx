"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { MessageBubble } from "@/components/inbox/message-bubble";
import { MessageComposer } from "@/components/inbox/message-composer";
import { ConversationStatusBadge, HandlerBadge } from "@/components/inbox/status-badge";
import type { UserRole } from "@/lib/auth/rbac";
import { contactDisplayName, contactInitials, formatDayLabel, formatPhone } from "@/lib/inbox/format";
import {
  useConversationMessages,
  useMessageStream,
  useSendMessage,
  useUpdateConversation,
} from "@/lib/inbox/queries";
import type { Conversation, Message } from "@/lib/inbox/types";

interface CurrentUser {
  id: string;
  role: UserRole;
}

export function MessageThread({
  businessId,
  conversation,
  currentUser,
  onBack,
  className,
}: {
  businessId: string;
  conversation: Conversation | null;
  currentUser: CurrentUser;
  onBack: () => void;
  className?: string;
}) {
  if (!conversation) {
    return (
      <div
        className={`flex-1 flex-col items-center justify-center gap-1 bg-slate-50 px-6 text-center ${className ?? "hidden md:flex"}`}
      >
        <p className="text-sm font-medium text-slate-600">Select a conversation</p>
        <p className="text-sm text-slate-400">
          Choose a conversation from the list to view its message history.
        </p>
      </div>
    );
  }

  return (
    <ActiveThread
      businessId={businessId}
      conversation={conversation}
      currentUser={currentUser}
      onBack={onBack}
      className={className}
    />
  );
}

function ActiveThread({
  businessId,
  conversation,
  currentUser,
  onBack,
  className,
}: {
  businessId: string;
  conversation: Conversation;
  currentUser: CurrentUser;
  onBack: () => void;
  className?: string;
}) {
  const messagesQuery = useConversationMessages(businessId, conversation.id);
  const sendMessage = useSendMessage(businessId);
  const updateConversation = useUpdateConversation(businessId);

  // SSE stream: injects new messages into the cache without waiting for the
  // next REST poll cycle.
  useMessageStream(businessId, conversation.id);

  const messages = messagesQuery.data ?? [];

  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    stickToBottomRef.current = true;
  }, [conversation.id]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node && stickToBottomRef.current) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages.length, conversation.id]);

  const handleScroll = () => {
    const node = scrollRef.current;
    if (!node) return;
    stickToBottomRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 120;
  };

  const isAssignedToMe = conversation.assigned_user_id === currentUser.id;
  const isOpen = conversation.status === "open" || conversation.status === "pending";
  const isClosed = conversation.status === "closed";

  const handleTakeOver = () => {
    updateConversation.mutate(
      { conversationId: conversation.id, payload: { status: "handoff", assigned_user_id: currentUser.id } },
      { onError: () => toast.error("Failed to take over the conversation.") },
    );
  };

  const handleHandBack = () => {
    updateConversation.mutate(
      { conversationId: conversation.id, payload: { status: "open", assigned_user_id: null } },
      { onError: () => toast.error("Failed to hand back the conversation.") },
    );
  };

  const handleClose = () => {
    updateConversation.mutate(
      { conversationId: conversation.id, payload: { status: "closed" } },
      { onError: () => toast.error("Failed to close the conversation.") },
    );
  };

  const handleReopen = () => {
    updateConversation.mutate(
      { conversationId: conversation.id, payload: { status: "open", assigned_user_id: null } },
      { onError: () => toast.error("Failed to reopen the conversation.") },
    );
  };

  const canTakeOver = !isClosed && !isAssignedToMe;
  const canHandBack = isAssignedToMe;

  return (
    <div className={`min-w-0 flex-1 flex-col ${className ?? "flex"}`}>
      {/* ── Thread header ─────────────────────────────────────────── */}
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Back to conversations"
            className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 md:hidden"
          >
            ←
          </button>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600">
            {contactInitials(conversation.contact_name, conversation.contact_phone)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">
              {contactDisplayName(conversation.contact_name, conversation.contact_phone)}
            </p>
            <p className="truncate text-xs text-slate-400">{formatPhone(conversation.contact_phone)}</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <ConversationStatusBadge status={conversation.status} />
          <HandlerBadge conversation={conversation} currentUserId={currentUser.id} />

          {canTakeOver && (
            <ActionButton
              onClick={handleTakeOver}
              disabled={updateConversation.isPending}
              variant="brand"
            >
              Take over
            </ActionButton>
          )}
          {canHandBack && !isClosed && (
            <ActionButton
              onClick={handleHandBack}
              disabled={updateConversation.isPending}
              variant="ghost"
            >
              Hand back to AI
            </ActionButton>
          )}
          {isOpen && (
            <ActionButton
              onClick={handleClose}
              disabled={updateConversation.isPending}
              variant="ghost"
            >
              Close
            </ActionButton>
          )}
          {isClosed && (
            <ActionButton
              onClick={handleReopen}
              disabled={updateConversation.isPending}
              variant="ghost"
            >
              Reopen
            </ActionButton>
          )}
        </div>
      </header>

      {/* ── Message history ────────────────────────────────────────── */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-slate-50 px-4 py-4"
      >
        {messagesQuery.isLoading ? (
          <ThreadSkeleton />
        ) : messagesQuery.isError ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <p className="text-sm font-medium text-slate-600">Couldn&apos;t load this conversation</p>
            <button
              type="button"
              onClick={() => messagesQuery.refetch()}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:border-slate-400"
            >
              Retry
            </button>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            No messages yet — say hello.
          </div>
        ) : (
          groupByDay(messages).map(([day, dayMessages]) => (
            <div key={day} className="space-y-3">
              <div className="flex justify-center">
                <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-500 shadow-sm">
                  {day}
                </span>
              </div>
              {dayMessages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
            </div>
          ))
        )}
      </div>

      {/* ── Composer ───────────────────────────────────────────────── */}
      <MessageComposer
        disabled={isClosed}
        disabledReason="This conversation is closed. Reopen it to send a reply."
        isSending={sendMessage.isPending}
        onSend={(text) =>
          sendMessage.mutate(
            { conversation, text },
            { onError: () => toast.error("Failed to send message. Please try again.") },
          )
        }
      />
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  variant,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled: boolean;
  variant: "brand" | "ghost";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
        variant === "brand"
          ? "border-brand-200 bg-brand-50 text-brand-700 hover:bg-brand-100"
          : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-800"
      }`}
    >
      {children}
    </button>
  );
}

function groupByDay(messages: Message[]): [string, Message[]][] {
  const groups = new Map<string, Message[]>();
  for (const message of messages) {
    const label = formatDayLabel(message.created_at);
    const bucket = groups.get(label);
    if (bucket) bucket.push(message);
    else groups.set(label, [message]);
  }
  return Array.from(groups.entries());
}

function ThreadSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className={`flex ${index % 2 === 0 ? "justify-start" : "justify-end"}`}>
          <div className="h-12 w-1/2 max-w-xs animate-pulse rounded-2xl bg-slate-200/70" />
        </div>
      ))}
    </div>
  );
}
