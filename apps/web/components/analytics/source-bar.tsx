import type { LeadSourceStat } from "@/lib/analytics/types";

interface Props {
  sources: LeadSourceStat[];
}

const SOURCE_COLORS: Record<string, string> = {
  whatsapp: "bg-green-500",
  web: "bg-blue-500",
  email: "bg-amber-500",
  referral: "bg-purple-500",
  other: "bg-slate-400",
  unknown: "bg-slate-300",
};

function colorForSource(source: string): string {
  return SOURCE_COLORS[source.toLowerCase()] ?? "bg-indigo-500";
}

export function SourceBar({ sources }: Props) {
  const total = sources.reduce((s, r) => s + r.count, 0);
  if (total === 0) {
    return <p className="text-sm text-slate-400">No leads in this period.</p>;
  }

  return (
    <div className="space-y-3">
      {sources.map((s) => {
        const pct = Math.round((s.count / total) * 100);
        return (
          <div key={s.source}>
            <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
              <span className="capitalize">{s.source}</span>
              <span className="font-medium">
                {s.count} <span className="text-slate-400">({pct}%)</span>
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-100">
              <div
                className={`h-2 rounded-full ${colorForSource(s.source)}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
