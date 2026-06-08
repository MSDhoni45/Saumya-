import { roleLabel } from "@/lib/auth/rbac";
import { getSession } from "@/lib/auth/session";

export default async function DashboardPage() {
  const session = await getSession();
  // The layout already redirects unauthenticated visitors — `session` is
  // guaranteed here, but TypeScript can't see across that boundary.
  if (!session) return null;

  const { user, business } = session;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Welcome back{user.full_name ? `, ${user.full_name}` : ""}</h1>
        <p className="mt-1 text-sm text-slate-500">
          Signed in as <span className="font-medium text-slate-700">{user.email}</span> ({roleLabel(user.role)})
          {business ? (
            <>
              {" "}
              at <span className="font-medium text-slate-700">{business.name}</span>
            </>
          ) : null}
          .
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Role" value={roleLabel(user.role)} />
        <SummaryCard label="Business" value={business?.name ?? "—"} />
        <SummaryCard label="Account created" value={new Date(user.created_at).toLocaleDateString()} />
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </div>
  );
}
