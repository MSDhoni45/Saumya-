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

  return <InboxView businessId={business.id} currentUser={{ id: user.id, role: user.role }} />;
}
