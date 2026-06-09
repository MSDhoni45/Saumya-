import { Suspense } from "react";
import { redirect } from "next/navigation";

import { InboxView } from "@/components/inbox/inbox-view";
import { getSession } from "@/lib/auth/session";

export default async function InboxPage() {
  const session = await getSession();
  // The layout already redirects unauthenticated visitors — defense-in-depth
  // for the same reason as the dashboard layout's own check.
  if (!session) redirect("/login");

  const { user, business } = session;

  if (!business) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-sm rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <p className="text-sm font-medium text-slate-700">No business linked</p>
          <p className="mt-1 text-sm text-slate-500">
            This account isn&apos;t associated with a business yet, so there&apos;s no inbox to show.
          </p>
        </div>
      </div>
    );
  }

  return (
    // Suspense required: InboxView calls useSearchParams() which opts the
    // subtree out of static rendering and needs a streaming boundary.
    <Suspense fallback={<InboxSkeleton />}>
      <InboxView businessId={business.id} currentUser={{ id: user.id, role: user.role }} />
    </Suspense>
  );
}

function InboxSkeleton() {
  return (
    <div className="flex h-full">
      <div className="flex w-full flex-col border-r border-slate-200 bg-white md:w-[360px]">
        <div className="shrink-0 space-y-3 border-b border-slate-200 p-4">
          <div className="h-6 w-16 animate-pulse rounded bg-slate-200" />
          <div className="h-9 w-full animate-pulse rounded-md bg-slate-100" />
          <div className="flex gap-1.5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-6 w-16 animate-pulse rounded-full bg-slate-100" />
            ))}
          </div>
        </div>
        <div className="flex-1 space-y-px p-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex animate-pulse items-start gap-3 rounded-md px-2 py-3">
              <div className="h-9 w-9 shrink-0 rounded-full bg-slate-200" />
              <div className="flex-1 space-y-2 pt-1">
                <div className="h-3 w-2/3 rounded bg-slate-200" />
                <div className="h-2.5 w-1/3 rounded bg-slate-100" />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="hidden flex-1 items-center justify-center bg-slate-50 md:flex">
        <p className="text-sm text-slate-400">Select a conversation</p>
      </div>
    </div>
  );
}
