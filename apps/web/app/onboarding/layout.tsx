import { redirect } from "next/navigation";

import { ErrorBoundary } from "@/components/error-boundary";
import { getSession } from "@/lib/auth/session";

export const metadata = { title: "Get started — WhatsAgent AI" };

export default async function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.business?.onboarding_completed) {
    redirect("/dashboard");
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      {/* Minimal header */}
      <header className="shrink-0 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <p className="text-sm font-bold tracking-tight text-slate-900">WhatsAgent AI</p>
          <p className="text-xs text-slate-400">Setting up your account</p>
        </div>
      </header>

      {/* Content */}
      <main className="flex flex-1 flex-col px-4 py-10">
        <div className="mx-auto w-full max-w-3xl flex-1">
          <ErrorBoundary>{children}</ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
