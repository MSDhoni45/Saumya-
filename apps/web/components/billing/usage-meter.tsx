"use client";

import type { Usage } from "@/lib/billing/types";

interface Props {
  usage: Usage;
}

export function UsageMeter({ usage }: Props) {
  const isUnlimited = usage.message_limit === null;
  const pct = usage.percent_used ?? 0;

  const barColor =
    pct >= 90
      ? "bg-red-500"
      : pct >= 70
        ? "bg-amber-400"
        : "bg-brand-500";

  const periodLabel = usage.period_start
    ? new Date(usage.period_start).toLocaleDateString("en-US", { month: "long", year: "numeric" })
    : "This month";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-1 flex items-baseline justify-between">
        <p className="text-sm font-medium text-slate-700">AI replies used</p>
        <p className="text-xs text-slate-400">{periodLabel}</p>
      </div>

      {isUnlimited ? (
        <div className="mt-2">
          <p className="text-2xl font-bold text-slate-900">
            {usage.message_count.toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-slate-500">Unlimited on Agency plan</p>
        </div>
      ) : (
        <>
          <div className="mt-2 flex items-baseline gap-1">
            <p className="text-2xl font-bold text-slate-900">
              {usage.message_count.toLocaleString()}
            </p>
            <p className="text-sm text-slate-400">
              / {usage.message_limit!.toLocaleString()}
            </p>
          </div>

          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full transition-all duration-500 ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>

          <div className="mt-1.5 flex justify-between text-xs text-slate-400">
            <span>{pct}% used</span>
            <span>{(usage.message_limit! - usage.message_count).toLocaleString()} remaining</span>
          </div>

          {pct >= 80 && (
            <p className={`mt-3 rounded-lg px-3 py-2 text-xs font-medium ${pct >= 90 ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
              {pct >= 90
                ? "You're almost out of AI replies for this month. Upgrade to avoid interruptions."
                : "Approaching your monthly limit. Consider upgrading soon."}
            </p>
          )}
        </>
      )}
    </div>
  );
}
