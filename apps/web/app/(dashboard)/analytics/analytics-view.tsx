"use client";

import { useState } from "react";

import { MetricCard } from "@/components/analytics/metric-card";
import { SourceBar } from "@/components/analytics/source-bar";
import { TrendChart } from "@/components/analytics/trend-chart";
import { useAnalyticsOverview } from "@/lib/analytics/queries";

interface Props {
  businessId: string;
}

const PERIOD_OPTIONS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

function msToDisplay(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function AnalyticsView({ businessId }: Props) {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useAnalyticsOverview(businessId, days);

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Analytics</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Performance overview for your WhatsApp AI workspace.
          </p>
        </div>
        <div className="flex rounded-lg border border-slate-200 bg-white overflow-hidden">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                days === opt.value
                  ? "bg-indigo-600 text-white"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load analytics data.
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      ) : data ? (
        <>
          {/* Metric cards */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            <MetricCard
              title="Conversations"
              value={data.conversations.value.toLocaleString()}
              changePct={data.conversations.change_pct}
              series={data.conversation_series}
              seriesColor="#6366f1"
            />
            <MetricCard
              title="Leads"
              value={data.leads.value.toLocaleString()}
              changePct={data.leads.change_pct}
              series={data.lead_series}
              seriesColor="#10b981"
            />
            <MetricCard
              title="Conversion Rate"
              value={`${data.conversion_rate.value.toFixed(1)}%`}
              subtitle="Conversations → Leads"
              changePct={data.conversion_rate.change_pct}
            />
            <MetricCard
              title="AI Response Time"
              value={msToDisplay(data.ai_response_time_ms)}
              subtitle={
                data.ai_response_time_p95_ms != null
                  ? `p95: ${msToDisplay(data.ai_response_time_p95_ms)}`
                  : "median"
              }
            />
            <MetricCard
              title="Human Takeovers"
              value={data.human_takeovers.toLocaleString()}
              subtitle={`${data.human_takeover_rate.toFixed(1)}% of conversations`}
            />
            <MetricCard
              title="Qualification Rate"
              value={`${data.qualification_rate.value.toFixed(1)}%`}
              subtitle="Leads qualified or won"
              changePct={data.qualification_rate.change_pct}
            />
          </div>

          {/* Charts row */}
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <TrendChart
                data={data.conversation_series}
                color="#6366f1"
                label="Daily Conversations"
                height={100}
              />
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <TrendChart
                data={data.lead_series}
                color="#10b981"
                label="Daily Leads"
                height={100}
              />
            </div>
          </div>

          {/* Lead sources */}
          {data.lead_sources.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-900">Lead Sources</h2>
              <SourceBar sources={data.lead_sources} />
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
