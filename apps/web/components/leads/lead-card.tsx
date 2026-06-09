"use client";

import { StageBadge } from "@/components/leads/stage-badge";
import { leadDisplayName, leadInitials, sourceLabel } from "@/lib/leads/format";
import { formatRelativeTime } from "@/lib/inbox/format";
import type { Lead } from "@/lib/leads/types";

export function LeadCard({
  lead,
  isSelected,
  onSelect,
}: {
  lead: Lead;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const displayName = leadDisplayName(lead);
  const initials = leadInitials(lead);

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
        {initials}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-medium text-slate-900">{displayName}</span>
          <span className="shrink-0 text-xs text-slate-400">{formatRelativeTime(lead.updated_at)}</span>
        </span>
        {(lead.email || lead.phone) && (
          <span className="mt-0.5 block truncate text-xs text-slate-500">
            {lead.email ?? lead.phone}
          </span>
        )}
        <span className="mt-1.5 flex items-center gap-2">
          <StageBadge stage={lead.stage} />
          <span className="text-[11px] text-slate-400">{sourceLabel(lead.source)}</span>
        </span>
      </span>
    </button>
  );
}
