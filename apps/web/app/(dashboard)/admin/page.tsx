import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";

import { ManualBillingForm } from "./manual-billing-form";

/**
 * Super-admin-only console for the pilot phase.
 *
 * Operator flips a paid plan onto a business out-of-band — used while
 * `BILLING_ENABLED=false` and Stripe/Razorpay are not connected yet. Mirrors
 * the API surface at `apps/api/app/api/v1/admin.py`. Server Component does
 * the role gate; the form is a client island for the mutation.
 */
export default async function AdminPage() {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }
  if (session.user.role !== "super_admin") {
    // Don't leak the route's existence; bounce to the regular dashboard.
    redirect("/dashboard");
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Operator console</h1>
        <p className="mt-1 text-sm text-slate-500">
          Manually activate or revert a business&apos;s plan during the pilot, before payment
          processors are wired in.
        </p>
      </header>

      <ManualBillingForm />

      <section className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
        <h2 className="font-semibold text-slate-900">Audit trail</h2>
        <p className="mt-2">
          Every activation and deactivation writes a row to <code>billing_events</code> tagged
          with your user id. Confirm in the database or via the billing-events query before
          telling the customer it&apos;s live.
        </p>
      </section>
    </div>
  );
}
