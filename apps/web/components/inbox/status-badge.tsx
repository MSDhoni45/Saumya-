import type { Conversation, ConversationStatus } from "@/lib/inbox/types";

const STATUS_STYLES: Record<ConversationStatus, { label: string; dot: string; text: string }> = {
  open: { label: "Open", dot: "bg-emerald-500", text: "text-emerald-700" },
  pending: { label: "Pending", dot: "bg-amber-500", text: "text-amber-700" },
  handoff: { label: "Handoff", dot: "bg-violet-500", text: "text-violet-700" },
  closed: { label: "Closed", dot: "bg-slate-400", text: "text-slate-500" },
};

export function ConversationStatusBadge({ status }: { status: ConversationStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${style.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} aria-hidden />
      {style.label}
    </span>
  );
}

const HANDLER_STYLES = {
  ai: "bg-brand-50 text-brand-700",
  you: "bg-emerald-50 text-emerald-700",
  teammate: "bg-slate-100 text-slate-600",
  unassigned: "bg-slate-100 text-slate-500",
} as const;

/**
 * Surfaces "who's driving this conversation right now" — derived purely from
 * `status`/`assigned_user_id` since there is no presence/team-directory
 * endpoint to resolve a teammate's display name (`(needs backend)`).
 */
export function HandlerBadge({
  conversation,
  currentUserId,
}: {
  conversation: Pick<Conversation, "status" | "assigned_user_id">;
  currentUserId: string;
}) {
  const { label, tone } = describeHandler(conversation, currentUserId);
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${HANDLER_STYLES[tone]}`}>{label}</span>;
}

function describeHandler(
  conversation: Pick<Conversation, "status" | "assigned_user_id">,
  currentUserId: string,
): { label: string; tone: keyof typeof HANDLER_STYLES } {
  if (conversation.assigned_user_id) {
    return conversation.assigned_user_id === currentUserId
      ? { label: "Assigned to you", tone: "you" }
      : { label: "Assigned to teammate", tone: "teammate" };
  }
  if (conversation.status === "closed") {
    return { label: "Closed", tone: "unassigned" };
  }
  return { label: "AI handling", tone: "ai" };
}
