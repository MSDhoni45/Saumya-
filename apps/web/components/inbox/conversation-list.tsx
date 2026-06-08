"use client";

import { useMemo, useState } from "react";

import { ConversationListItem } from "@/components/inbox/conversation-list-item";
import type { Conversation, ConversationStatus } from "@/lib/inbox/types";

const STATUS_FILTERS: { value: ConversationStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "pending", label: "Pending" },
  { value: "handoff", label: "Handoff" },
  { value: "closed", label: "Closed" },
];

const HANDLER_FILTERS = [
  { value: "all", label: "All" },
  { value: "mine", label: "Assigned to me" },
  { value: "ai", label: "AI-handled" },
  { value: "unassigned", label: "Unassigned" },
] as const;

type HandlerFilter = (typeof HANDLER_FILTERS)[number]["value"];

export function ConversationList({
  conversations,
  isLoading,
  isError,
  onRetry,
  selectedConversationId,
  onSelectConversation,
  currentUserId,
  className,
}: {
  conversations: Conversation[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
  currentUserId: string;
  className?: string;
}) {
  const [search, setSearch] = useState("");
  const [statusFilters, setStatusFilters] = useState<Set<ConversationStatus>>(() => new Set());
  const [handlerFilter, setHandlerFilter] = useState<HandlerFilter>("all");

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();

    return conversations.filter((conversation) => {
      if (statusFilters.size > 0 && !statusFilters.has(conversation.status)) return false;
      if (handlerFilter === "mine" && conversation.assigned_user_id !== currentUserId) return false;
      if (handlerFilter === "unassigned" && conversation.assigned_user_id !== null) return false;
      if (handlerFilter === "ai" && (conversation.assigned_user_id !== null || conversation.status === "closed")) return false;

      if (query) {
        const haystack = `${conversation.contact_name ?? ""} ${conversation.contact_phone}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }

      return true;
    });
  }, [conversations, search, statusFilters, handlerFilter, currentUserId]);

  const toggleStatusFilter = (status: ConversationStatus) => {
    setStatusFilters((previous) => {
      const next = new Set(previous);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  };

  const clearFilters = () => {
    setSearch("");
    setStatusFilters(new Set());
    setHandlerFilter("all");
  };

  const activeFilterCount = statusFilters.size + (handlerFilter !== "all" ? 1 : 0);
  const hasAnyActiveRefinement = activeFilterCount > 0 || search.trim().length > 0;

  return (
    <div className={`w-full flex-col border-r border-slate-200 bg-white md:w-[360px] ${className ?? "flex"}`}>
      <div className="shrink-0 space-y-3 border-b border-slate-200 p-4">
        <h1 className="text-lg font-semibold text-slate-900">Inbox</h1>

        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name or phone number"
          aria-label="Search conversations"
          className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />

        <div className="flex flex-wrap items-center gap-1.5">
          {STATUS_FILTERS.map((filter) => (
            <FilterChip
              key={filter.value}
              label={filter.label}
              active={statusFilters.has(filter.value)}
              onClick={() => toggleStatusFilter(filter.value)}
            />
          ))}
          <span className="mx-0.5 h-4 w-px bg-slate-200" aria-hidden />
          {HANDLER_FILTERS.map((filter) => (
            <FilterChip
              key={filter.value}
              label={filter.label}
              active={handlerFilter === filter.value}
              onClick={() => setHandlerFilter(filter.value)}
            />
          ))}
          {activeFilterCount > 0 && (
            <button type="button" onClick={clearFilters} className="text-xs font-medium text-slate-400 hover:text-slate-600">
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <ConversationListSkeleton />
        ) : isError ? (
          <EmptyState
            title="Couldn't load conversations"
            description="Check your connection and try again."
            action={{ label: "Retry", onClick: onRetry }}
          />
        ) : conversations.length === 0 ? (
          <EmptyState
            title="No conversations yet"
            description="Conversations will appear here once your WhatsApp number starts receiving messages."
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No matches"
            description="Try a different search term or clear your filters."
            action={hasAnyActiveRefinement ? { label: "Clear filters", onClick: clearFilters } : undefined}
          />
        ) : (
          filtered.map((conversation) => (
            <ConversationListItem
              key={conversation.id}
              conversation={conversation}
              isSelected={conversation.id === selectedConversationId}
              currentUserId={currentUserId}
              onSelect={() => onSelectConversation(conversation.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
        active
          ? "border-brand-600 bg-brand-50 text-brand-700"
          : "border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700"
      }`}
    >
      {label}
    </button>
  );
}

function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <p className="text-sm text-slate-400">{description}</p>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-2 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:border-slate-400 hover:text-slate-800"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

function ConversationListSkeleton() {
  return (
    <div className="space-y-0.5 p-2">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex animate-pulse items-start gap-3 rounded-md px-2 py-3">
          <div className="h-9 w-9 shrink-0 rounded-full bg-slate-200" />
          <div className="flex-1 space-y-2 pt-1">
            <div className="h-3 w-2/3 rounded bg-slate-200" />
            <div className="h-2.5 w-1/3 rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
}
