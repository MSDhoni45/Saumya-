"use client";

import { ConversationStatusBadge, HandlerBadge } from "@/components/inbox/status-badge";
import { contactDisplayName, contactInitials, formatRelativeTime } from "@/lib/inbox/format";
import type { Conversation } from "@/lib/inbox/types";

const SENDER_PREFIX: Record<string, string> = {
  ai: "AI: ",
  agent: "You: ",
  contact: "",
  system: "",
};

export function ConversationListItem({
  conversation,
  isSelected,
  currentUserId,
  onSelect,
}: {
  conversation: Conversation;
  isSelected: boolean;
  currentUserId: string;
  onSelect: () => void;
}) {
  const prefix = conversation.last_sender_type ? (SENDER_PREFIX[conversation.last_sender_type] ?? "") : "";
  const preview = conversation.last_message_content
    ? `${prefix}${conversation.last_message_content}`
    : null;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={isSelected}
      className={`flex w-full items-start gap-3 border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50 ${
        isSelected ? "bg-brand-50/70 hover:bg-brand-50/70" : ""
      }`}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600">
        {contactInitials(conversation.contact_name, conversation.contact_phone)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-medium text-slate-900">
            {contactDisplayName(conversation.contact_name, conversation.contact_phone)}
          </span>
          <span className="shrink-0 text-xs text-slate-400">{formatRelativeTime(conversation.last_message_at)}</span>
        </span>
        {preview ? (
          <span className="mt-0.5 block truncate text-xs text-slate-500">{preview}</span>
        ) : null}
        <span className="mt-1.5 flex items-center gap-2">
          <ConversationStatusBadge status={conversation.status} />
          <span className="text-slate-300" aria-hidden>
            ·
          </span>
          <HandlerBadge conversation={conversation} currentUserId={currentUserId} />
        </span>
      </span>
    </button>
  );
}
