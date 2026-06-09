"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";

import { CheckoutModal } from "@/components/billing/checkout-modal";
import { PlanCard } from "@/components/billing/plan-card";
import { UsageMeter } from "@/components/billing/usage-meter";
import {
  useCancelSubscription,
  usePlans,
  useReactivateSubscription,
  useSubscription,
  useUsage,
} from "@/lib/billing/queries";
import type { Plan } from "@/lib/billing/types";

interface Props {
  businessId: string;
}

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  active: { label: "Active", className: "bg-green-50 text-green-700" },
  trialing: { label: "Trial", className: "bg-blue-50 text-blue-700" },
  past_due: { label: "Payment overdue", className: "bg-red-50 text-red-700" },
  cancelled: { label: "Cancelled", className: "bg-slate-100 text-slate-500" },
  paused: { label: "Paused", className: "bg-amber-50 text-amber-700" },
};

export function BillingView({ businessId }: Props) {
  const searchParams = useSearchParams();
  const successParam = searchParams.get("success");

  const { data: plans, isLoading: plansLoading } = usePlans(businessId);
  const { data: sub } = useSubscription(businessId);
  const { data: usage } = useUsage(businessId);
  const cancelMutation = useCancelSubscription(businessId);
  const reactivateMutation = useReactivateSubscription(businessId);

  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);

  const statusInfo = sub ? (STATUS_LABELS[sub.status] ?? STATUS_LABELS.active) : null;
  const isPaidActive = sub && sub.plan !== "free" && sub.status === "active";
  const isCancelling = sub?.cancel_at_period_end;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8">
      {/* Success banner */}
      {successParam && (
        <div className="rounded-xl bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          Your subscription has been activated. Welcome to your new plan!
        </div>
      )}

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Billing & Plans</h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage your subscription, usage, and payment details.
        </p>
      </div>

      {/* Current plan card */}
      {sub && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Current plan
              </p>
              <h2 className="mt-1 text-xl font-bold text-slate-900 capitalize">{sub.plan}</h2>
              {sub.current_period_end && (
                <p className="mt-1 text-sm text-slate-500">
                  {isCancelling ? "Cancels" : "Renews"} on{" "}
                  {new Date(sub.current_period_end).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {statusInfo && (
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusInfo.className}`}>
                  {statusInfo.label}
                </span>
              )}
              {sub.payment_provider && (
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500 capitalize">
                  via {sub.payment_provider}
                </span>
              )}
            </div>
          </div>

          {/* Cancellation warning */}
          {isCancelling && (
            <div className="mt-4 flex items-center justify-between rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
              <p className="text-sm text-amber-800">
                Your subscription is scheduled to cancel at the end of this billing period.
              </p>
              <button
                onClick={() => reactivateMutation.mutate()}
                disabled={reactivateMutation.isPending}
                className="ml-4 shrink-0 rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
              >
                {reactivateMutation.isPending ? "Reactivating…" : "Keep subscription"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Usage meter */}
      {usage && <UsageMeter usage={usage} />}

      {/* Plans grid */}
      <div>
        <h2 className="mb-4 text-base font-semibold text-slate-900">Available plans</h2>
        {plansLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-72 animate-pulse rounded-xl bg-slate-100" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {(plans ?? []).map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onSelect={setSelectedPlan}
                disabled={cancelMutation.isPending || reactivateMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>

      {/* Danger zone — cancel */}
      {isPaidActive && !isCancelling && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="text-sm font-semibold text-slate-900">Cancel subscription</h3>
          <p className="mt-1 text-sm text-slate-500">
            Your plan remains active until the end of the current billing period. You won't be charged
            again after cancellation.
          </p>
          <button
            onClick={() => {
              if (confirm("Are you sure you want to cancel? Your plan stays active until the billing period ends.")) {
                cancelMutation.mutate();
              }
            }}
            disabled={cancelMutation.isPending}
            className="mt-4 rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            {cancelMutation.isPending ? "Cancelling…" : "Cancel subscription"}
          </button>
        </div>
      )}

      {/* Checkout modal */}
      {selectedPlan && (
        <CheckoutModal
          plan={selectedPlan}
          businessId={businessId}
          onClose={() => setSelectedPlan(null)}
          onSuccess={() => setSelectedPlan(null)}
        />
      )}
    </div>
  );
}
