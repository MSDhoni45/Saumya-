import { redirect } from "next/navigation";

import { ErrorBoundary } from "@/components/error-boundary";
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
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="shrink-0 border-b border-slate-200 bg-white">
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
            <a href="/inbox" className="font-medium text-slate-700 hover:text-brand-600">
              Inbox
            </a>
            <a href="/leads" className="font-medium text-slate-700 hover:text-brand-600">
              Leads
            </a>
            <a href="/settings/whatsapp" className="font-medium text-slate-700 hover:text-brand-600">
              Settings
            </a>
            <SignOutButton />
          </nav>
        </div>
      </header>
      {/* `min-h-0` lets full-height workspace pages (e.g. the inbox's split
          panes) size themselves to the remaining viewport instead of being
          stretched to their content's height by the flex column. Ordinary
          content pages apply their own max-width/padding and simply scroll
          within this region. */}
      <main className="min-h-0 flex-1 overflow-y-auto">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </div>
  );
}
