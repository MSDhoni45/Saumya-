import type { DayStat } from "@/lib/analytics/types";
import { Sparkline } from "./sparkline";

interface Props {
  title: string;
  value: string;
  subtitle?: string;
  changePct?: number | null;
  series?: DayStat[];
  seriesColor?: string;
}

function TrendBadge({ pct }: { pct: number }) {
  const up = pct >= 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-medium ${
        up ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
      }`}
    >
      {up ? "↑" : "↓"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export function MetricCard({ title, value, subtitle, changePct, series, seriesColor }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
      <div className="mt-2 flex items-end justify-between gap-2">
        <div>
          <p className="text-2xl font-bold text-slate-900">{value}</p>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          {changePct != null && (
            <div className="mt-1.5">
              <TrendBadge pct={changePct} />
              <span className="ml-1 text-xs text-slate-400">vs prev. period</span>
            </div>
          )}
        </div>
        {series && series.length > 1 && (
          <Sparkline data={series} color={seriesColor ?? "#6366f1"} />
        )}
      </div>
    </div>
  );
}
