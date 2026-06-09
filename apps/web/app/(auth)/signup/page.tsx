"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { AuthField, AuthFormError, AuthSubmitButton } from "@/components/auth/auth-field";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { SessionUser } from "@/lib/auth/rbac";

const signupSchema = z.object({
  full_name: z.string().min(1, "Enter your full name"),
  business_name: z.string().min(1, "Enter your business name"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters"),
});

type SignupValues = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const [checkEmail, setCheckEmail] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({ resolver: zodResolver(signupSchema) });

  const onSubmit = async (values: SignupValues) => {
    setFormError(null);
    try {
      // Becomes the `business_admin` of a brand-new business named
      // `business_name` — see app/api/v1/auth.py::signup.
      await apiFetch<{ user: SessionUser }>("/auth/signup", { method: "POST", json: values });
      router.push("/onboarding?step=1");
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 202) {
        setCheckEmail(true);
      } else if (error instanceof ApiError && error.status === 409) {
        setFormError("An account with this email already exists.");
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    }
  };

  if (checkEmail) {
    return (
      <div className="space-y-2 text-center">
        <h1 className="text-lg font-semibold text-slate-900">Check your email</h1>
        <p className="text-sm text-slate-500">
          We&apos;ve sent a confirmation link to your inbox — open it to activate your account and sign in.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-500">You&apos;ll be set up as the admin of your business.</p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <AuthFormError message={formError} />
        <AuthField label="Full name" autoComplete="name" {...register("full_name")} error={errors.full_name} />
        <AuthField
          label="Business name"
          autoComplete="organization"
          {...register("business_name")}
          error={errors.business_name}
        />
        <AuthField label="Email" type="email" autoComplete="email" {...register("email")} error={errors.email} />
        <AuthField
          label="Password"
          type="password"
          autoComplete="new-password"
          {...register("password")}
          error={errors.password}
        />
        <AuthSubmitButton pending={isSubmitting}>Create account</AuthSubmitButton>
      </form>

      <p className="text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
          Sign in
        </Link>
      </p>
    </div>
  );
}
