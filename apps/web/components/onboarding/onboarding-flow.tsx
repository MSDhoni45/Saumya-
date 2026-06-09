"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { StepIndicator } from "@/components/onboarding/step-indicator";
import { StepBusiness } from "@/components/onboarding/step-business";
import { StepWhatsApp } from "@/components/onboarding/step-whatsapp";
import { StepKnowledge } from "@/components/onboarding/step-knowledge";
import { StepAgent } from "@/components/onboarding/step-agent";
import { StepTest } from "@/components/onboarding/step-test";
import { StepGoLive } from "@/components/onboarding/step-golive";
import type { OnboardingStep } from "@/lib/onboarding/types";

const TOTAL_STEPS = 6;

export function OnboardingFlow({
  businessId,
  businessName,
  industry,
  currentUserId,
}: {
  businessId: string;
  businessName: string;
  industry: string | null;
  currentUserId: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const rawStep = Number(searchParams.get("step") ?? "1");
  const step = (rawStep >= 1 && rawStep <= TOTAL_STEPS ? rawStep : 1) as OnboardingStep;

  const goTo = useCallback(
    (s: number) => {
      const clamped = Math.max(1, Math.min(TOTAL_STEPS, s));
      router.push(`/onboarding?step=${clamped}`, { scroll: false });
    },
    [router],
  );

  const next = useCallback(() => goTo(step + 1), [step, goTo]);
  const back = useCallback(() => goTo(step - 1), [step, goTo]);
  const skip = useCallback(() => goTo(step + 1), [step, goTo]);

  return (
    <div className="flex min-h-full flex-col">
      {/* Progress bar */}
      <div className="mb-8 flex justify-center">
        <StepIndicator current={step} />
      </div>

      {/* Step content */}
      <div className="mx-auto w-full max-w-2xl flex-1">
        {step === 1 && (
          <StepBusiness businessId={businessId} onNext={next} />
        )}
        {step === 2 && (
          <StepWhatsApp businessId={businessId} onNext={next} onBack={back} onSkip={skip} />
        )}
        {step === 3 && (
          <StepKnowledge businessId={businessId} onNext={next} onBack={back} onSkip={skip} />
        )}
        {step === 4 && (
          <StepAgent businessId={businessId} onNext={next} onBack={back} onSkip={skip} />
        )}
        {step === 5 && (
          <StepTest businessId={businessId} onNext={next} onBack={back} onSkip={skip} />
        )}
        {step === 6 && (
          <StepGoLive
            businessId={businessId}
            businessName={businessName}
            industry={industry}
            onBack={back}
          />
        )}
      </div>
    </div>
  );
}
