"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { AuthField, AuthFormError, AuthSubmitButton } from "@/components/auth/auth-field";
import { apiFetch } from "@/lib/api/client";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, "Use at least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

type RecoveryState = "verifying" | "ready" | "invalid" | "done";

/**
 * The emailed reset link lands here with a recovery token in the URL —
 * Supabase's browser client exchanges it for a short-lived "recovery"
 * session and fires `onAuthStateChange("PASSWORD_RECOVERY", session)`.
 * We hand that session's access token to the backend (which performs the
 * actual password update via the GoTrue admin API — see
 * app/services/auth_service.py::update_password) rather than calling
 * `supabase.auth.updateUser` directly, so every credential mutation flows
 * through one audited backend surface.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const [state, setState] = useState<RecoveryState>("verifying");
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createSupabaseBrowserClient();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY" && session?.access_token) {
        setAccessToken(session.access_token);
        setState("ready");
      }
    });

    // If the link's session was already established before this listener
    // attached (fast navigations), check for it directly as a fallback.
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.access_token && state === "verifying") {
        setAccessToken(data.session.access_token);
        setState("ready");
      }
    });

    const timeout = setTimeout(() => setState((current) => (current === "verifying" ? "invalid" : current)), 5000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema) });

  const onSubmit = async (values: ResetPasswordValues) => {
    if (!accessToken) return;
    setFormError(null);
    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        json: { access_token: accessToken, new_password: values.password },
      });
      setState("done");
      setTimeout(() => router.push("/login"), 2000);
    } catch {
      setFormError("This reset link is invalid or has expired. Request a new one.");
    }
  };

  if (state === "verifying") {
    return <p className="text-center text-sm text-slate-500">Verifying your reset link…</p>;
  }

  if (state === "invalid") {
    return (
      <div className="space-y-2 text-center">
        <h1 className="text-lg font-semibold text-slate-900">Link invalid or expired</h1>
        <p className="text-sm text-slate-500">Reset links are single-use and time-limited — request a fresh one.</p>
        <Link href="/forgot-password" className="inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
          Request a new link
        </Link>
      </div>
    );
  }

  if (state === "done") {
    return (
      <div className="space-y-2 text-center">
        <h1 className="text-lg font-semibold text-slate-900">Password updated</h1>
        <p className="text-sm text-slate-500">Redirecting you to sign in…</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Set a new password</h1>
        <p className="mt-1 text-sm text-slate-500">Choose something you haven&apos;t used before.</p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <AuthFormError message={formError} />
        <AuthField
          label="New password"
          type="password"
          autoComplete="new-password"
          {...register("password")}
          error={errors.password}
        />
        <AuthField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          {...register("confirm_password")}
          error={errors.confirm_password}
        />
        <AuthSubmitButton pending={isSubmitting}>Update password</AuthSubmitButton>
      </form>
    </div>
  );
}
