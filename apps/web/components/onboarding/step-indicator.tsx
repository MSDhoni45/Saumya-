import { STEP_META } from "@/lib/onboarding/types";
import type { OnboardingStep } from "@/lib/onboarding/types";

export function StepIndicator({ current }: { current: OnboardingStep }) {
  return (
    <div className="flex items-center gap-0">
      {STEP_META.map(({ step }, idx) => {
        const done = step < current;
        const active = step === current;
        return (
          <div key={step} className="flex items-center">
            {idx > 0 && (
              <div
                className={`h-px w-8 shrink-0 transition-colors sm:w-12 ${
                  done ? "bg-brand-500" : "bg-slate-200"
                }`}
              />
            )}
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-all ${
                done
                  ? "bg-brand-500 text-white"
                  : active
                    ? "bg-brand-600 text-white ring-4 ring-brand-100"
                    : "bg-slate-100 text-slate-400"
              }`}
              aria-current={active ? "step" : undefined}
            >
              {done ? "✓" : step}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function StepHeader({ current }: { current: OnboardingStep }) {
  const meta = STEP_META.find((m) => m.step === current)!;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-widest text-brand-600">
        Step {current} of {STEP_META.length}
      </p>
      <h1 className="mt-1 text-2xl font-bold text-slate-900">{meta.title}</h1>
      <p className="mt-1 text-sm text-slate-500">{meta.description}</p>
    </div>
  );
}
