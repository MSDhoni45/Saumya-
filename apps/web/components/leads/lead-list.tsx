"use client";

import { useCallback } from "react";

import { LeadCard } from "@/components/leads/lead-card";
import { STAGE_ORDER, STAGE_STYLES } from "@/lib/leads/format";
import { useLeads } from "@/lib/leads/queries";
import type { LeadFilters, LeadStage } from "@/lib/leads/types";

const SORT_OPTIONS = [
  { value: "updated_desc", label: "Last updated" },
  { value: "created_asc", label: "Oldest first" },
  { value: "stage_asc", label: "Stage" },
] as const;

export function LeadList({
  businessId,
  filters,
  selectedLeadId,
  onSelectLead,
  onFilterChange,
  className,
}: {
  businessId: string;
  filters: LeadFilters;
  selectedLeadId: string | null;
  onSelectLead: (id: string) => void;
  onFilterChange: (patch: Partial<LeadFilters>) => void;
  className?: string;
}) {
  const query = useLeads(businessId, filters);
  const { items = [], total = 0, pages = 1 } = query.data ?? {};

  const toggleStage = useCallback(
    (stage: LeadStage) => {
      const next = new Set(filters.stage);
      if (next.has(stage)) next.delete(stage);
      else next.add(stage);
      onFilterChange({ stage: next, page: 1 });
    },
    [filters.stage, onFilterChange],
  );

  const clearFilters = () =>
    onFilterChange({ q: "", stage: new Set(), source: new Set(), assigned: "all", page: 1 });

  const hasActiveFilters =
    filters.q || filters.stage.size > 0 || filters.source.size > 0 || filters.assigned !== "all";

  return (
    <div className={`w-full flex-col border-r border-slate-200 bg-white md:w-[360px] ${className ?? "flex"}`}>
      {/* ── Header / filters ─────────────────────────────────────────── */}
      <div className="shrink-0 space-y-3 border-b border-slate-200 p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-slate-900">Leads</h1>
          {total > 0 && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              {total}
            </span>
          )}
        </div>

        <input
          type="search"
          value={filters.q}
          onChange={(e) => onFilterChange({ q: e.target.value, page: 1 })}
          placeholder="Search name, phone, email…"
          aria-label="Search leads"
          className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />

        {/* Stage filter chips */}
        <div className="flex flex-wrap gap-1.5">
          {STAGE_ORDER.map((stage) => {
            const s = STAGE_STYLES[stage];
            const active = filters.stage.has(stage);
            return (
              <button
                key={stage}
                type="button"
                onClick={() => toggleStage(stage)}
                aria-pressed={active}
                className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                  active
                    ? `${s.bg} ${s.border} ${s.text}`
                    : "border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700"
                }`}
              >
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Assignment + sort row */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-slate-200 text-xs font-medium overflow-hidden">
            {(["all", "me", "unassigned"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => onFilterChange({ assigned: v, page: 1 })}
                className={`px-2.5 py-1.5 capitalize transition ${
                  filters.assigned === v
                    ? "bg-slate-800 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                {v === "all" ? "All" : v === "me" ? "Mine" : "Unassigned"}
              </button>
            ))}
          </div>
          <select
            value={filters.sort}
            onChange={(e) => onFilterChange({ sort: e.target.value as LeadFilters["sort"], page: 1 })}
            className="ml-auto rounded-md border border-slate-200 bg-white py-1.5 pl-2 pr-6 text-xs text-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
            aria-label="Sort leads"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-xs font-medium text-slate-400 hover:text-slate-600"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* ── Lead rows ─────────────────────────────────────────────────── */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {query.isLoading ? (
          <LeadListSkeleton />
        ) : query.isError ? (
          <EmptyState
            title="Couldn't load leads"
            description="Check your connection and try again."
            action={{ label: "Retry", onClick: () => query.refetch() }}
          />
        ) : items.length === 0 ? (
          hasActiveFilters ? (
            <EmptyState
              title="No matching leads"
              description="Try a different search or clear your filters."
              action={{ label: "Clear filters", onClick: clearFilters }}
            />
          ) : (
            <EmptyState
              title="No leads yet"
              description="Leads appear here once your AI agent qualifies a WhatsApp contact."
            />
          )
        ) : (
          items.map((lead) => (
            <LeadCard
              key={lead.id}
              lead={lead}
              isSelected={lead.id === selectedLeadId}
              onSelect={() => onSelectLead(lead.id)}
            />
          ))
        )}
      </div>

      {/* ── Pagination ────────────────────────────────────────────────── */}
      {pages > 1 && (
        <div className="flex shrink-0 items-center justify-between border-t border-slate-200 px-4 py-2.5">
          <button
            type="button"
            onClick={() => onFilterChange({ page: filters.page - 1 })}
            disabled={filters.page <= 1}
            className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="text-xs text-slate-500">
            Page {filters.page} of {pages}
          </span>
          <button
            type="button"
            onClick={() => onFilterChange({ page: filters.page + 1 })}
            disabled={filters.page >= pages}
            className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:border-slate-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
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

function LeadListSkeleton() {
  return (
    <div className="space-y-0.5 p-2">
      {Array.from({ length: 7 }).map((_, i) => (
        <div key={i} className="flex animate-pulse items-start gap-3 rounded-md px-2 py-3">
          <div className="h-9 w-9 shrink-0 rounded-full bg-slate-200" />
          <div className="flex-1 space-y-2 pt-1">
            <div className="h-3 w-2/3 rounded bg-slate-200" />
            <div className="h-2.5 w-1/2 rounded bg-slate-100" />
            <div className="h-5 w-16 rounded-full bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
}
