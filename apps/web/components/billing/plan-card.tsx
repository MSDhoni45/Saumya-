"use client";

import type { Plan } from "@/lib/billing/types";

interface Props {
  plan: Plan;
  onSelect: (plan: Plan) => void;
  disabled?: boolean;
}

const HIGHLIGHT_PLAN = "growth";

export function PlanCard({ plan, onSelect, disabled }: Props) {
  const priceINR = plan.price_inr_paise / 100;
  const priceUSD = plan.price_usd_cents / 100;
  const isUnlimited = plan.message_limit === null;
  const isFree = plan.price_inr_paise === 0;
  const isHighlighted = plan.id === HIGHLIGHT_PLAN;

  return (
    <div
      className={[
        "relative flex flex-col rounded-xl border p-6 transition-shadow",
        isHighlighted
          ? "border-brand-500 shadow-md ring-2 ring-brand-500/30 bg-white"
          : "border-slate-200 bg-white hover:shadow-sm",
        plan.is_current ? "opacity-80" : "",
      ].join(" ")}
    >
      {isHighlighted && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-500 px-3 py-0.5 text-xs font-semibold text-white">
          Most popular
        </span>
      )}

      <div className="mb-4">
        <h3 className="text-base font-semibold text-slate-900">{plan.name}</h3>
        <p className="mt-1 text-sm text-slate-500">{plan.description}</p>
      </div>

      <div className="mb-6">
        {isFree ? (
          <p className="text-3xl font-bold text-slate-900">Free</p>
        ) : (
          <div>
            <p className="text-3xl font-bold text-slate-900">
              ₹{priceINR.toLocaleString("en-IN")}
              <span className="text-sm font-normal text-slate-500">/month</span>
            </p>
            <p className="mt-0.5 text-xs text-slate-400">${priceUSD}/mo (USD)</p>
          </div>
        )}
      </div>

      <ul className="mb-6 space-y-2 text-sm text-slate-600">
        <li className="flex items-center gap-2">
          <CheckIcon />
          {isUnlimited
            ? "Unlimited AI replies"
            : `${plan.message_limit!.toLocaleString()} AI replies / month`}
        </li>
        <li className="flex items-center gap-2">
          <CheckIcon />
          WhatsApp integration
        </li>
        <li className="flex items-center gap-2">
          <CheckIcon />
          Lead CRM & qualification
        </li>
        {plan.id !== "free" && (
          <li className="flex items-center gap-2">
            <CheckIcon />
            Priority support
          </li>
        )}
        {plan.id === "agency" && (
          <li className="flex items-center gap-2">
            <CheckIcon />
            Dedicated account manager
          </li>
        )}
      </ul>

      <div className="mt-auto">
        {plan.is_current ? (
          <div className="rounded-lg border border-slate-200 px-4 py-2 text-center text-sm font-medium text-slate-500">
            Current plan
          </div>
        ) : isFree ? null : (
          <button
            onClick={() => onSelect(plan)}
            disabled={disabled}
            className={[
              "w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors",
              isHighlighted
                ? "bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-50"
                : "border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50",
            ].join(" ")}
          >
            Upgrade to {plan.name}
          </button>
        )}
      </div>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg className="h-4 w-4 shrink-0 text-brand-500" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
        clipRule="evenodd"
      />
    </svg>
  );
}
