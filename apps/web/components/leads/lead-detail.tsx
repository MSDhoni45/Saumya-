"use client";

import { toast } from "sonner";

import { LeadFields } from "@/components/leads/lead-fields";
import { StageSelector } from "@/components/leads/stage-badge";
import { LeadTimeline } from "@/components/leads/lead-timeline";
import { leadDisplayName, leadInitials, sourceLabel } from "@/lib/leads/format";
import { formatRelativeTime } from "@/lib/inbox/format";
import { useLead, useUpdateLead } from "@/lib/leads/queries";
import type { LeadStage, LeadUpdatePayload } from "@/lib/leads/types";

export function LeadDetail({
  businessId,
  leadId,
  currentUserId,
  onBack,
  className,
}: {
  businessId: string;
  leadId: string | null;
  currentUserId: string;
  onBack: () => void;
  className?: string;
}) {
  if (!leadId) {
    return (
      <div
        className={`flex-1 flex-col items-center justify-center gap-1 bg-slate-50 px-6 text-center ${className ?? "hidden md:flex"}`}
      >
        <p className="text-sm font-medium text-slate-600">Select a lead</p>
        <p className="text-sm text-slate-400">
          Choose a lead from the list to view their details and activity.
        </p>
      </div>
    );
  }

  return (
    <ActiveDetail
      businessId={businessId}
      leadId={leadId}
      currentUserId={currentUserId}
      onBack={onBack}
      className={className}
    />
  );
}

function ActiveDetail({
  businessId,
  leadId,
  currentUserId,
  onBack,
  className,
}: {
  businessId: string;
  leadId: string;
  currentUserId: string;
  onBack: () => void;
  className?: string;
}) {
  const leadQuery = useLead(businessId, leadId);
  const updateLead = useUpdateLead(businessId);
  const lead = leadQuery.data;

  const handleUpdate = (payload: LeadUpdatePayload) => {
    updateLead.mutate(
      { leadId, payload, actorId: currentUserId },
      { onError: () => toast.error("Failed to save changes.") },
    );
  };

  const handleStageChange = (stage: LeadStage) => handleUpdate({ stage });

  if (leadQuery.isLoading || !lead) {
    return <DetailSkeleton className={className} onBack={onBack} />;
  }

  if (leadQuery.isError) {
    return (
      <div className={`flex-1 flex-col items-center justify-center gap-2 bg-slate-50 ${className ?? "flex"}`}>
        <p className="text-sm text-slate-600">Failed to load lead.</p>
        <button
          type="button"
          onClick={() => leadQuery.refetch()}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:border-slate-400"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className={`min-w-0 flex-1 flex-col overflow-y-auto bg-slate-50 ${className ?? "flex"}`}>
      {/* ── Header ───────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Back to leads"
            className="mt-0.5 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 md:hidden"
          >
            ←
          </button>
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600">
            {leadInitials(lead)}
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-base font-semibold text-slate-900">{leadDisplayName(lead)}</h2>
            <p className="mt-0.5 text-xs text-slate-400">
              {sourceLabel(lead.source)} · Last activity {formatRelativeTime(lead.updated_at)}
            </p>
          </div>
        </div>

        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-slate-500">Stage</p>
          <StageSelector
            current={lead.stage as LeadStage}
            onSelect={handleStageChange}
            disabled={updateLead.isPending}
          />
        </div>

        {lead.conversation_id && (
          <a
            href={`/inbox?c=${lead.conversation_id}`}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            View WhatsApp conversation →
          </a>
        )}
      </div>

      {/* ── Contact fields ────────────────────────────────────────────── */}
      <section className="shrink-0 bg-white px-5 py-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Contact</p>
        <LeadFields lead={lead} onSave={handleUpdate} isSaving={updateLead.isPending} />
      </section>

      {/* ── AI qualification notes ────────────────────────────────────── */}
      {lead.notes && (
        <section className="shrink-0 border-t border-slate-100 bg-white px-5 py-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            AI qualification notes
          </p>
          <p className="whitespace-pre-wrap text-sm text-slate-600">{lead.notes}</p>
        </section>
      )}

      {/* ── Timeline ─────────────────────────────────────────────────── */}
      <section className="flex-1 border-t border-slate-100 px-5 py-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Activity</p>
        <LeadTimeline businessId={businessId} leadId={leadId} currentUserId={currentUserId} />
      </section>
    </div>
  );
}

function DetailSkeleton({ className, onBack }: { className?: string; onBack: () => void }) {
  return (
    <div className={`min-w-0 flex-1 flex-col overflow-y-auto bg-slate-50 ${className ?? "flex"}`}>
      <div className="shrink-0 border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex items-start gap-3">
          <button type="button" onClick={onBack} className="mt-0.5 rounded-md p-1.5 text-slate-400 md:hidden">←</button>
          <div className="h-10 w-10 animate-pulse rounded-full bg-slate-200" />
          <div className="flex-1 space-y-2 pt-1">
            <div className="h-4 w-40 animate-pulse rounded bg-slate-200" />
            <div className="h-3 w-24 animate-pulse rounded bg-slate-100" />
          </div>
        </div>
        <div className="mt-4 flex gap-1.5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-7 w-16 animate-pulse rounded-full bg-slate-100" />
          ))}
        </div>
      </div>
      <div className="space-y-2 bg-white px-5 py-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-3 w-24 animate-pulse rounded bg-slate-100" />
            <div className="h-3 w-40 animate-pulse rounded bg-slate-200" />
          </div>
        ))}
      </div>
    </div>
  );
}
