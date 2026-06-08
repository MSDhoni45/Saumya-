"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { AuthField, AuthFormError, AuthSubmitButton } from "@/components/auth/auth-field";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { SessionUser } from "@/lib/auth/rbac";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (values: LoginValues) => {
    setFormError(null);
    try {
      await apiFetch<{ user: SessionUser }>("/auth/login", { method: "POST", json: values });
      const redirectTo = searchParams.get("redirect") ?? "/dashboard";
      router.push(redirectTo);
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setFormError("Invalid email or password.");
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Sign in</h1>
        <p className="mt-1 text-sm text-slate-500">Welcome back — enter your details to continue.</p>
      </div>

      {searchParams.get("confirmed") === "1" && (
        <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          Email confirmed — you can sign in now.
        </div>
      )}

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <AuthFormError message={formError} />
        <AuthField label="Email" type="email" autoComplete="email" {...register("email")} error={errors.email} />
        <AuthField
          label="Password"
          type="password"
          autoComplete="current-password"
          {...register("password")}
          error={errors.password}
        />
        <div className="flex justify-end">
          <Link href="/forgot-password" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            Forgot password?
          </Link>
        </div>
        <AuthSubmitButton pending={isSubmitting}>Sign in</AuthSubmitButton>
      </form>

      <p className="text-center text-sm text-slate-500">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-medium text-brand-600 hover:text-brand-700">
          Create one
        </Link>
      </p>
    </div>
  );
}
