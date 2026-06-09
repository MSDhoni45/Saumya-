import type { DayStat } from "@/lib/analytics/types";

interface Props {
  data: DayStat[];
  color?: string;
  width?: number;
  height?: number;
}

export function Sparkline({ data, color = "#6366f1", width = 120, height = 36 }: Props) {
  if (data.length < 2) return null;

  const counts = data.map((d) => d.count);
  const max = Math.max(...counts, 1);
  const min = Math.min(...counts);
  const range = max - min || 1;

  const padX = 2;
  const padY = 4;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const points = data.map((d, i) => {
    const x = padX + (i / (data.length - 1)) * plotW;
    const y = padY + (1 - (d.count - min) / range) * plotH;
    return `${x},${y}`;
  });

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
