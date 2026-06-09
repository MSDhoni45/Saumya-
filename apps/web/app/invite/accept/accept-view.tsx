"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAcceptInvite, useInviteDetails } from "@/lib/team/queries";
import type { AcceptInviteResponse } from "@/lib/team/types";
import { ApiError } from "@/lib/api/client";

const ROLE_LABELS: Record<string, string> = {
  business_admin: "Admin",
  team_member: "Team Member",
};

export function AcceptView() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const router = useRouter();

  const { data: invite, isLoading, error: detailsError } = useInviteDetails(token);

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState<AcceptInviteResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const acceptMutation = useAcceptInvite(token);

  if (!token) {
    return <ErrorCard title="Invalid link" message="No invitation token found in this URL." />;
  }

  if (isLoading) {
    return (
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center">
        <p className="text-sm text-slate-400">Loading invitation…</p>
      </div>
    );
  }

  if (detailsError || !invite) {
    return <ErrorCard title="Invite not found" message="This invitation link is invalid or has been removed." />;
  }

  if (!invite.is_valid) {
    const msg = invite.expired
      ? "This invitation has expired. Ask your admin to send a new one."
      : "This invitation has already been used or revoked.";
    return <ErrorCard title="Invite unavailable" message={msg} />;
  }

  if (accepted) {
    return (
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
          <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-slate-900">Welcome aboard!</h2>
        <p className="mt-2 text-sm text-slate-500">{accepted.message}</p>
        <button
          onClick={() => router.push("/dashboard")}
          className="mt-6 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Go to dashboard
        </button>
      </div>
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    acceptMutation.mutate(
      { full_name: fullName || undefined, password: password || undefined },
      {
        onSuccess: (data) => setAccepted(data),
        onError: (err) => {
          if (err instanceof ApiError && typeof err.body === "object" && err.body !== null) {
            const body = err.body as Record<string, unknown>;
            setFormError(String(body.detail ?? "Failed to accept invitation"));
          } else {
            setFormError("Something went wrong. Please try again.");
          }
        },
      },
    );
  }

  const roleLabel = ROLE_LABELS[invite.role] ?? invite.role;

  return (
    <div className="w-full max-w-md">
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="bg-indigo-600 px-6 py-5">
          <h1 className="text-lg font-bold text-white">WhatsAgent AI</h1>
        </div>
        <div className="px-6 py-6">
          <h2 className="text-lg font-semibold text-slate-900">You&apos;re invited!</h2>
          <p className="mt-2 text-sm text-slate-600">
            {invite.invited_by_name ? (
              <>
                <strong>{invite.invited_by_name}</strong> has invited you to join{" "}
                <strong>{invite.business_name}</strong> as a <strong>{roleLabel}</strong>.
              </>
            ) : (
              <>
                You&apos;ve been invited to join <strong>{invite.business_name}</strong> as a{" "}
                <strong>{roleLabel}</strong>.
              </>
            )}
          </p>
          <p className="mt-1 text-xs text-slate-400">Joining as: {invite.email}</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Full name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your full name"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Password{" "}
                <span className="font-normal text-slate-400">
                  (leave blank if you already have an account)
                </span>
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 8 characters"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {formError && (
              <p className="text-sm text-red-600">{formError}</p>
            )}

            <button
              type="submit"
              disabled={acceptMutation.isPending}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {acceptMutation.isPending ? "Joining…" : "Accept invitation"}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-slate-400">
            Already have an account?{" "}
            <a href={`/login?redirect=/invite/accept?token=${token}`} className="text-indigo-600 hover:underline">
              Sign in first
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

function ErrorCard({ title, message }: { title: string; message: string }) {
  return (
    <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
        <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 text-sm text-slate-500">{message}</p>
      <a
        href="/login"
        className="mt-6 inline-block rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
      >
        Back to login
      </a>
    </div>
  );
}
