"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { StepHeader } from "@/components/onboarding/step-indicator";
export { StepHeader };
import { useBusiness, useUpdateBusiness } from "@/lib/onboarding/queries";

const INDUSTRIES = [
  "Real Estate",
  "E-commerce",
  "Healthcare",
  "Education",
  "Finance",
  "Technology",
  "Hospitality",
  "Retail",
  "Consulting",
  "Marketing",
  "Legal",
  "Other",
];

const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "America/New_York", label: "Eastern Time (ET)" },
  { value: "America/Chicago", label: "Central Time (CT)" },
  { value: "America/Denver", label: "Mountain Time (MT)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  { value: "America/Sao_Paulo", label: "São Paulo (BRT)" },
  { value: "America/Toronto", label: "Toronto (ET)" },
  { value: "Europe/London", label: "London (GMT/BST)" },
  { value: "Europe/Paris", label: "Paris (CET/CEST)" },
  { value: "Europe/Berlin", label: "Berlin (CET/CEST)" },
  { value: "Europe/Madrid", label: "Madrid (CET/CEST)" },
  { value: "Asia/Dubai", label: "Dubai (GST)" },
  { value: "Asia/Kolkata", label: "Mumbai / Delhi (IST)" },
  { value: "Asia/Singapore", label: "Singapore (SGT)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
  { value: "Asia/Shanghai", label: "Shanghai / Beijing (CST)" },
  { value: "Australia/Sydney", label: "Sydney (AEST/AEDT)" },
  { value: "Pacific/Auckland", label: "Auckland (NZST/NZDT)" },
];

interface FormValues {
  name: string;
  industry: string;
  timezone: string;
}

export function StepBusiness({
  businessId,
  onNext,
}: {
  businessId: string;
  onNext: () => void;
}) {
  const businessQuery = useBusiness(businessId);
  const updateBusiness = useUpdateBusiness(businessId);

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    defaultValues: { name: "", industry: "", timezone: "UTC" },
  });

  useEffect(() => {
    if (businessQuery.data) {
      reset({
        name: businessQuery.data.name ?? "",
        industry: businessQuery.data.industry ?? "",
        timezone: businessQuery.data.timezone ?? "UTC",
      });
    }
  }, [businessQuery.data, reset]);

  const onSubmit = async (values: FormValues) => {
    try {
      await updateBusiness.mutateAsync({
        name: values.name.trim(),
        industry: values.industry || null,
        timezone: values.timezone,
      });
      onNext();
    } catch {
      toast.error("Failed to save business details. Please try again.");
    }
  };

  if (businessQuery.isLoading) {
    return <StepSkeleton />;
  }

  return (
    <div className="space-y-8">
      <StepHeader current={1} />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">
            Business name <span className="text-red-500">*</span>
          </label>
          <input
            {...register("name", { required: "Business name is required" })}
            type="text"
            placeholder="e.g. Acme Corp"
            className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
          {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Industry</label>
          <select
            {...register("industry")}
            className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          >
            <option value="">Select an industry…</option>
            {INDUSTRIES.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">Timezone</label>
          <select
            {...register("timezone")}
            className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          >
            {TIMEZONES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <StepActions>
          <PrimaryButton type="submit" pending={isSubmitting || updateBusiness.isPending}>
            Continue →
          </PrimaryButton>
        </StepActions>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable action bar primitives (used in other steps too)
// ---------------------------------------------------------------------------

export function StepActions({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center justify-end gap-3 pt-2">{children}</div>;
}

export function PrimaryButton({
  children,
  pending,
  disabled,
  onClick,
  type = "button",
}: {
  children: React.ReactNode;
  pending?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={pending || disabled}
      className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {pending ? "Saving…" : children}
    </button>
  );
}

export function SecondaryButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-slate-200 px-5 py-2.5 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50"
    >
      {children}
    </button>
  );
}

export function SkipButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-sm text-slate-400 hover:text-slate-600"
    >
      Skip for now
    </button>
  );
}

function StepSkeleton() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
        <div className="h-7 w-48 animate-pulse rounded bg-slate-200" />
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="h-3 w-28 animate-pulse rounded bg-slate-200" />
          <div className="h-10 w-full animate-pulse rounded-lg bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
