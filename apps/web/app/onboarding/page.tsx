import { redirect } from "next/navigation";
import { Suspense } from "react";

import { OnboardingFlow } from "@/components/onboarding/onboarding-flow";
import { getSession } from "@/lib/auth/session";

function OnboardingSkeleton() {
  return (
    <div className="space-y-10">
      <div className="flex justify-center gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            {i > 0 && <div className="h-px w-8 bg-slate-200 sm:w-12" />}
            <div className="h-8 w-8 animate-pulse rounded-full bg-slate-200" />
          </div>
        ))}
      </div>
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="space-y-2">
          <div className="h-3 w-20 animate-pulse rounded bg-slate-200" />
          <div className="h-7 w-48 animate-pulse rounded bg-slate-200" />
          <div className="h-4 w-64 animate-pulse rounded bg-slate-100" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-3 w-28 animate-pulse rounded bg-slate-200" />
            <div className="h-10 animate-pulse rounded-lg bg-slate-100" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default async function OnboardingPage() {
  const session = await getSession();
  if (!session) redirect("/login");

  const { user, business } = session;
  if (!business) redirect("/login");

  return (
    <Suspense fallback={<OnboardingSkeleton />}>
      <OnboardingFlow
        businessId={business.id}
        businessName={business.name}
        industry={business.industry}
        currentUserId={user.id}
      />
    </Suspense>
  );
}
