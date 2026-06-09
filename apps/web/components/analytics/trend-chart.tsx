import type { DayStat } from "@/lib/analytics/types";

interface Props {
  data: DayStat[];
  color?: string;
  label?: string;
  height?: number;
}

export function TrendChart({ data, color = "#6366f1", label, height = 80 }: Props) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-400">No data.</p>;
  }

  const counts = data.map((d) => d.count);
  const max = Math.max(...counts, 1);

  return (
    <div>
      {label && (
        <p className="mb-2 text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
      )}
      <div className="flex items-end gap-0.5" style={{ height }}>
        {data.map((d, i) => {
          const h = Math.max((d.count / max) * height, d.count > 0 ? 2 : 1);
          return (
            <div
              key={i}
              className="group relative flex-1 cursor-default rounded-sm transition-opacity hover:opacity-80"
              style={{ height: h, backgroundColor: color, opacity: d.count === 0 ? 0.15 : 0.85 }}
              title={`${d.date}: ${d.count}`}
            />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-xs text-slate-400">
        <span>{data[0]?.date?.slice(5)}</span>
        <span>{data[data.length - 1]?.date?.slice(5)}</span>
      </div>
    </div>
  );
}
