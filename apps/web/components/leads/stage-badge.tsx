import { STAGE_ORDER, STAGE_STYLES, stageStyle } from "@/lib/leads/format";
import type { LeadStage } from "@/lib/leads/types";

export function StageBadge({ stage }: { stage: string }) {
  const s = stageStyle(stage);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.bg} ${s.border} ${s.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {s.label}
    </span>
  );
}

/**
 * Horizontal stage progression bar — all stages rendered as chips, current
 * stage highlighted. Clicking a chip fires `onSelect` so it doubles as the
 * inline stage selector in the detail header.
 */
export function StageSelector({
  current,
  onSelect,
  disabled,
}: {
  current: LeadStage;
  onSelect: (stage: LeadStage) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Lead stage">
      {STAGE_ORDER.map((stage) => {
        const s = STAGE_STYLES[stage];
        const isActive = stage === current;
        return (
          <button
            key={stage}
            type="button"
            onClick={() => !isActive && onSelect(stage)}
            disabled={disabled || isActive}
            aria-pressed={isActive}
            className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
              isActive
                ? `${s.bg} ${s.border} ${s.text} cursor-default`
                : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700 disabled:cursor-not-allowed"
            }`}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
