import { redirect } from "next/navigation";

import { roleLabel } from "@/lib/auth/rbac";
import { getSession } from "@/lib/auth/session";
import { SignOutButton } from "@/components/auth/sign-out-button";

/**
 * Protected shell for the authenticated product surface.
 *
 * Middleware already redirects unauthenticated requests away from this route
 * group (see middleware.ts) — this `redirect` is defense-in-depth for the
 * Server Component render itself (e.g. a session that expired between the
 * middleware check and this layout resolving `/auth/me`).
 */
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  const { user, business } = session;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-slate-900">{business?.name ?? "WhatsAgent AI"}</p>
            <p className="text-xs text-slate-500">
              {user.full_name ?? user.email} · {roleLabel(user.role)}
            </p>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <a href="/dashboard" className="font-medium text-slate-700 hover:text-brand-600">
              Dashboard
            </a>
            <SignOutButton />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
