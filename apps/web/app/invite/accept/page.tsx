import { Suspense } from "react";

import { AcceptView } from "./accept-view";

export const metadata = { title: "Accept Invitation — WhatsAgent AI" };

export default function AcceptInvitePage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
        <AcceptView />
      </Suspense>
    </div>
  );
}
