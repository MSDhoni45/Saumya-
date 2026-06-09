"use client";

import { useState } from "react";

import { useCheckout } from "@/lib/billing/queries";
import type { CheckoutPlanId, Plan, RazorpayCheckoutResponse } from "@/lib/billing/types";

interface Props {
  plan: Plan;
  businessId: string;
  onClose: () => void;
  onSuccess: () => void;
}

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Razorpay: any;
  }
}

async function loadRazorpayScript(): Promise<void> {
  if (typeof window === "undefined" || window.Razorpay) return;
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Razorpay script"));
    document.body.appendChild(script);
  });
}

export function CheckoutModal({ plan, businessId, onClose, onSuccess }: Props) {
  const [loading, setLoading] = useState<"stripe" | "razorpay" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const checkout = useCheckout(businessId);

  const priceINR = plan.price_inr_paise / 100;
  const priceUSD = plan.price_usd_cents / 100;

  async function handleStripe() {
    setLoading("stripe");
    setError(null);
    try {
      const result = await checkout.mutateAsync({
        plan: plan.id as CheckoutPlanId,
        provider: "stripe",
      });
      if (result.provider === "stripe") {
        window.location.href = result.checkout_url;
      }
    } catch {
      setError("Failed to start Stripe checkout. Please try again.");
      setLoading(null);
    }
  }

  async function handleRazorpay() {
    setLoading("razorpay");
    setError(null);
    try {
      const result = await checkout.mutateAsync({
        plan: plan.id as CheckoutPlanId,
        provider: "razorpay",
      });
      if (result.provider !== "razorpay") return;

      const rp = result as RazorpayCheckoutResponse;
      await loadRazorpayScript();

      const rzp = new window.Razorpay({
        key: rp.razorpay_key_id,
        subscription_id: rp.razorpay_subscription_id,
        name: "WhatsAgent AI",
        description: `${plan.name} Plan — ₹${priceINR.toLocaleString("en-IN")}/month`,
        prefill: {},
        theme: { color: "#6366f1" },
        handler: () => {
          onSuccess();
          onClose();
        },
        modal: {
          ondismiss: () => setLoading(null),
        },
      });
      rzp.open();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open Razorpay checkout.");
      setLoading(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Upgrade to {plan.name}
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">{plan.description}</p>
          </div>
          <button
            onClick={onClose}
            className="ml-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        {/* Price summary */}
        <div className="bg-slate-50 px-6 py-4">
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-slate-900">
              ₹{priceINR.toLocaleString("en-IN")}
            </span>
            <span className="text-sm text-slate-500">/month</span>
            <span className="ml-auto text-xs text-slate-400">(${priceUSD} USD)</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {plan.message_limit === null
              ? "Unlimited AI replies per month"
              : `Up to ${plan.message_limit.toLocaleString()} AI replies per month`}
          </p>
        </div>

        {/* Payment methods */}
        <div className="space-y-3 p-6">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Choose payment method
          </p>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}

          <button
            onClick={handleRazorpay}
            disabled={loading !== null}
            className="flex w-full items-center gap-3 rounded-xl border-2 border-[#2d6be4] bg-white px-4 py-3 text-left transition hover:bg-blue-50 disabled:opacity-50"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#2d6be4]">
              <svg viewBox="0 0 24 24" className="h-5 w-5 fill-white">
                <path d="M7 3h10a1 1 0 011 1v3H6V4a1 1 0 011-1zM5 9h14v11a1 1 0 01-1 1H6a1 1 0 01-1-1V9zm5 2v6l4-3-4-3z" />
              </svg>
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-900">Pay with Razorpay</p>
              <p className="text-xs text-slate-500">UPI, cards, net banking — ₹{priceINR.toLocaleString("en-IN")}/mo</p>
            </div>
            {loading === "razorpay" && <Spinner />}
          </button>

          <button
            onClick={handleStripe}
            disabled={loading !== null}
            className="flex w-full items-center gap-3 rounded-xl border-2 border-[#635bff] bg-white px-4 py-3 text-left transition hover:bg-violet-50 disabled:opacity-50"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#635bff]">
              <svg viewBox="0 0 24 24" className="h-5 w-5 fill-white">
                <path d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm-9 11H5v-2h6v2zm8 0h-6v-2h6v2zm0-4H5V9h14v2z" />
              </svg>
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-900">Pay with Stripe</p>
              <p className="text-xs text-slate-500">Credit / debit card — ${priceUSD}/mo</p>
            </div>
            {loading === "stripe" && <Spinner />}
          </button>
        </div>

        <p className="border-t border-slate-100 px-6 py-3 text-center text-xs text-slate-400">
          Cancel anytime · Secure payment
        </p>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin text-slate-400" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
