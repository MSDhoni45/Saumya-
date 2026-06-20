"use client";

import { useXAnalytics } from "@/lib/x/queries";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-5 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

const STATUS_COLOURS: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  reviewed: "bg-blue-100 text-blue-700",
  sent: "bg-indigo-100 text-indigo-700",
  dm_sent: "bg-violet-100 text-violet-700",
  replied: "bg-green-100 text-green-700",
  converted: "bg-emerald-100 text-emerald-700",
  skipped: "bg-red-100 text-red-600",
};

export function XDashboardView({ businessId }: { businessId: string }) {
  const { data, isLoading, error } = useXAnalytics(businessId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-400">
        Loading analytics…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <p className="text-sm text-red-500">
          Could not load analytics — make sure your X account is connected.
        </p>
        <a href="/x/connect" className="mt-2 text-sm text-slate-600 underline">
          Connect X Account
        </a>
      </div>
    );
  }

  const { outreach, posts, searches, top_leads } = data;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">X Automation Dashboard</h1>
        <div className="flex gap-3 text-sm">
          <a href="/x/connect" className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-600 hover:bg-slate-50">Accounts</a>
          <a href="/x/searches" className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-600 hover:bg-slate-50">Searches</a>
          <a href="/x/outreach" className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-600 hover:bg-slate-50">Outreach</a>
          <a href="/x/posts" className="rounded-lg bg-slate-900 px-3 py-1.5 text-white hover:bg-slate-700">Posts</a>
        </div>
      </div>

      {/* Outreach funnel */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Outreach Funnel</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total prospects" value={outreach.total} />
          <StatCard label="Avg AI score" value={outreach.avg_score ?? "—"} sub="out of 100" />
          <StatCard label="DMs sent (7d)" value={outreach.dm_sent_last_7d} />
          <StatCard label="Replies received" value={outreach.replied} />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(outreach.by_status).map(([status, count]) => (
            <span
              key={status}
              className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_COLOURS[status] ?? "bg-slate-100 text-slate-600"}`}
            >
              {status}: {count}
            </span>
          ))}
        </div>
      </section>

      {/* Posts + Searches */}
      <div className="grid grid-cols-2 gap-6">
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Posts</h2>
          <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
            {Object.entries(posts.by_status).map(([s, n]) => (
              <div key={s} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span className="capitalize text-slate-600">{s}</span>
                <span className="font-semibold text-slate-900">{n}</span>
              </div>
            ))}
            {Object.keys(posts.by_status).length === 0 && (
              <p className="px-4 py-3 text-sm text-slate-400">No posts yet.</p>
            )}
          </div>
          <a href="/x/posts" className="mt-2 block text-xs text-slate-500 hover:text-slate-900">Manage posts →</a>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Lead Searches</h2>
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-4 space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">Total configs</span>
              <span className="font-semibold">{searches.total}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Active</span>
              <span className="font-semibold text-green-600">{searches.active}</span>
            </div>
          </div>
          <a href="/x/searches" className="mt-2 block text-xs text-slate-500 hover:text-slate-900">Manage searches →</a>
        </section>
      </div>

      {/* Top leads */}
      {top_leads.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Top Prospects by AI Score</h2>
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-100 bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 text-left">Account</th>
                  <th className="px-4 py-2.5 text-left">Followers</th>
                  <th className="px-4 py-2.5 text-left">Score</th>
                  <th className="px-4 py-2.5 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {top_leads.map((lead) => (
                  <tr key={lead.username} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-medium text-slate-900">@{lead.username}</td>
                    <td className="px-4 py-2.5 text-slate-500">
                      {lead.followers_count?.toLocaleString() ?? "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-semibold text-violet-600">{lead.ai_score}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLOURS[lead.status] ?? "bg-slate-100 text-slate-600"}`}>
                        {lead.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <a href="/x/outreach" className="mt-2 block text-xs text-slate-500 hover:text-slate-900">View all outreach →</a>
        </section>
      )}
    </div>
  );
}
