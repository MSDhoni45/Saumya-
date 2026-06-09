import { redirect } from "next/navigation";
import { Suspense } from "react";

import { LeadsView } from "@/components/leads/leads-view";
import { getSession } from "@/lib/auth/session";

export const metadata = { title: "Leads" };

function LeadsSkeleton() {
  return (
    <div className="flex h-full">
      <div className="w-full flex-col border-r border-slate-200 bg-white md:w-[360px] flex">
        <div className="shrink-0 space-y-3 border-b border-slate-200 p-4">
          <div className="h-6 w-20 animate-pulse rounded bg-slate-200" />
          <div className="h-9 w-full animate-pulse rounded-md bg-slate-100" />
          <div className="flex gap-1.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-7 w-16 animate-pulse rounded-full bg-slate-100" />
            ))}
          </div>
        </div>
        <div className="flex-1 space-y-0.5 p-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="flex animate-pulse items-start gap-3 rounded-md px-2 py-3">
              <div className="h-9 w-9 shrink-0 rounded-full bg-slate-200" />
              <div className="flex-1 space-y-2 pt-1">
                <div className="h-3 w-2/3 rounded bg-slate-200" />
                <div className="h-2.5 w-1/2 rounded bg-slate-100" />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="hidden flex-1 items-center justify-center bg-slate-50 md:flex">
        <p className="text-sm text-slate-400">Select a lead to view details</p>
      </div>
    </div>
  );
}

export default async function LeadsPage() {
  const session = await getSession();
  if (!session) redirect("/login");

  const { user, business } = session;
  if (!business) redirect("/onboarding");

  return (
    <div className="flex h-full flex-col">
      <Suspense fallback={<LeadsSkeleton />}>
        <LeadsView businessId={business.id} currentUserId={user.id} />
      </Suspense>
    </div>
  );
}
