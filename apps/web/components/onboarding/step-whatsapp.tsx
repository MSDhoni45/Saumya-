"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { PrimaryButton, SecondaryButton, SkipButton, StepActions, StepHeader } from "@/components/onboarding/step-business";
import { useConnectWhatsApp, useDisconnectWhatsApp, useWhatsAppAccounts } from "@/lib/inbox/queries";

interface FormValues {
  waba_id: string;
  phone_number_id: string;
  access_token: string;
  display_name: string;
}

export function StepWhatsApp({
  businessId,
  onNext,
  onBack,
  onSkip,
}: {
  businessId: string;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}) {
  const accountsQuery = useWhatsAppAccounts(businessId);
  const connectWhatsApp = useConnectWhatsApp(businessId);
  const disconnectWhatsApp = useDisconnectWhatsApp(businessId);
  const [showForm, setShowForm] = useState(false);

  const accounts = accountsQuery.data ?? [];
  const connected = accounts.filter((a) => a.status === "connected");

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormValues>();

  const onSubmit = async (values: FormValues) => {
    try {
      await connectWhatsApp.mutateAsync({
        waba_id: values.waba_id.trim(),
        phone_number_id: values.phone_number_id.trim(),
        access_token: values.access_token.trim(),
        display_name: values.display_name.trim() || undefined,
      });
      reset();
      setShowForm(false);
      toast.success("WhatsApp account connected.");
    } catch {
      toast.error("Failed to connect. Check your credentials and try again.");
    }
  };

  return (
    <div className="space-y-8">
      <StepHeader current={2} />

      {/* Connected accounts */}
      {connected.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-700">Connected accounts</p>
          {connected.map((account) => (
            <div
              key={account.id}
              className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium text-slate-900">
                  {account.display_name ?? account.phone_number}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">{account.phone_number}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1 text-xs font-medium text-emerald-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Active
                </span>
                <button
                  type="button"
                  onClick={() =>
                    disconnectWhatsApp.mutate(account.id, {
                      onError: () => toast.error("Failed to disconnect account."),
                    })
                  }
                  className="text-xs text-slate-400 hover:text-red-500"
                >
                  Disconnect
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add account form toggle */}
      {!showForm && (
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-200 px-4 py-5 text-sm font-medium text-slate-500 transition hover:border-brand-300 hover:text-brand-600"
        >
          + Add WhatsApp account
        </button>
      )}

      {showForm && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-sm font-semibold text-slate-800">Connect WhatsApp Business Account</p>

          <FormField label="WABA ID" error={errors.waba_id?.message}>
            <input
              {...register("waba_id", { required: "Required" })}
              placeholder="123456789012345"
              className={inputClass}
            />
          </FormField>

          <FormField label="Phone Number ID" error={errors.phone_number_id?.message}>
            <input
              {...register("phone_number_id", { required: "Required" })}
              placeholder="123456789012345"
              className={inputClass}
            />
          </FormField>

          <FormField label="Permanent access token" error={errors.access_token?.message}>
            <input
              {...register("access_token", { required: "Required" })}
              type="password"
              placeholder="EAAxxxxxxx…"
              className={inputClass}
            />
          </FormField>

          <FormField label="Display name (optional)">
            <input
              {...register("display_name")}
              placeholder="My Business WhatsApp"
              className={inputClass}
            />
          </FormField>

          <div className="flex justify-end gap-2 pt-1">
            <SecondaryButton onClick={() => { setShowForm(false); reset(); }}>Cancel</SecondaryButton>
            <PrimaryButton type="submit" pending={isSubmitting || connectWhatsApp.isPending}>
              Connect
            </PrimaryButton>
          </div>
        </form>
      )}

      <StepActions>
        <SkipButton onClick={onSkip} />
        <SecondaryButton onClick={onBack}>← Back</SecondaryButton>
        <PrimaryButton onClick={onNext} disabled={connected.length === 0 && accounts.length === 0}>
          Continue →
        </PrimaryButton>
      </StepActions>
    </div>
  );
}

function FormField({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      {children}
      {error && <p className="mt-0.5 text-xs text-red-500">{error}</p>}
    </div>
  );
}

const inputClass =
  "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";
