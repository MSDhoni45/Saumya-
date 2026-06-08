"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { AuthField, AuthFormError, AuthSubmitButton } from "@/components/auth/auth-field";
import { apiFetch } from "@/lib/api/client";

const forgotPasswordSchema = z.object({
  email: z.string().email("Enter a valid email address"),
});

type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export default function ForgotPasswordPage() {
  const [formError, setFormError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema) });

  const onSubmit = async (values: ForgotPasswordValues) => {
    setFormError(null);
    try {
      const redirect_to = `${window.location.origin}/reset-password`;
      await apiFetch("/auth/forgot-password", { method: "POST", json: { ...values, redirect_to } });
      // The backend always returns success here regardless of whether the
      // address is registered — never let this page reveal account existence.
      setSent(true);
    } catch {
      setFormError("Something went wrong. Please try again.");
    }
  };

  if (sent) {
    return (
      <div className="space-y-2 text-center">
        <h1 className="text-lg font-semibold text-slate-900">Check your email</h1>
        <p className="text-sm text-slate-500">
          If an account exists for that address, we&apos;ve sent a link to reset your password.
        </p>
        <Link href="/login" className="inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Reset your password</h1>
        <p className="mt-1 text-sm text-slate-500">
          Enter your email and we&apos;ll send you a link to get back into your account.
        </p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <AuthFormError message={formError} />
        <AuthField label="Email" type="email" autoComplete="email" {...register("email")} error={errors.email} />
        <AuthSubmitButton pending={isSubmitting}>Send reset link</AuthSubmitButton>
      </form>

      <p className="text-center text-sm text-slate-500">
        <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
