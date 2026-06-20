"use client";

import { useState } from "react";
import {
  useXOutreach,
  useXAccounts,
  useSendXDm,
  useSendXReply,
  useUpdateXOutreach,
} from "@/lib/x/queries";
import type { XOutreach } from "@/lib/x/types";

const SCORE_COLOR = (s: number | null) => {
  if (s === null) return "text-slate-400";
  if (s >= 80) return "text-green-600 font-bold";
  if (s >= 60) return "text-violet-600 font-semibold";
  return "text-slate-500";
};

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  reviewed: "bg-blue-100 text-blue-700",
  sent: "bg-indigo-100 text-indigo-700",
  dm_sent: "bg-violet-100 text-violet-700",
  replied: "bg-green-100 text-green-700",
  converted: "bg-emerald-100 text-emerald-700",
  skipped: "bg-red-50 text-red-500",
};

function OutreachRow({
  item,
  accountId,
  onSendDm,
  onSendReply,
  onSkip,
  isSending,
}: {
  item: XOutreach;
  accountId: string | null;
  onSendDm: (id: string) => void;
  onSendReply: (id: string) => void;
  onSkip: (id: string) => void;
  isSending: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const canAct = accountId && item.status === "pending";

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-slate-50"
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="px-4 py-3">
          <p className="font-medium text-slate-900">@{item.username}</p>
          {item.display_name && <p className="text-xs text-slate-400">{item.display_name}</p>}
        </td>
        <td className="px-4 py-3 text-sm text-slate-500">
          {item.followers_count?.toLocaleString() ?? "—"}
        </td>
        <td className={`px-4 py-3 text-sm ${SCORE_COLOR(item.ai_score)}`}>
          {item.ai_score ?? "—"}
        </td>
        <td className="px-4 py-3">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[item.status] ?? "bg-slate-100 text-slate-600"}`}>
            {item.status}
          </span>
        </td>
        <td className="px-4 py-3">
          <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
            {canAct && (
              <>
                <button
                  onClick={() => onSendDm(item.id)}
                  disabled={isSending}
                  className="rounded bg-violet-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-violet-700 disabled:opacity-50"
                >
                  Send DM
                </button>
                <button
                  onClick={() => onSendReply(item.id)}
                  disabled={isSending}
                  className="rounded border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Reply Tweet
                </button>
                <button
                  onClick={() => onSkip(item.id)}
                  disabled={isSending}
                  className="rounded px-2.5 py-1 text-xs text-slate-400 hover:text-slate-700 disabled:opacity-50"
                >
                  Skip
                </button>
              </>
            )}
            {item.status === "replied" && (
              <span className="text-xs text-green-600">Got reply!</span>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="bg-slate-50 px-4 pb-3 text-xs text-slate-600">
            {item.profile_bio && <p className="mb-1 italic">"{item.profile_bio}"</p>}
            {item.tweet_text && (
              <p className="mb-1">
                <span className="font-medium">Tweet:</span> {item.tweet_text}
              </p>
            )}
            {item.ai_score_reason && (
              <p className="mb-1">
                <span className="font-medium">AI reason:</span> {item.ai_score_reason}
              </p>
            )}
            {item.outreach_message && (
              <p>
                <span className="font-medium">Draft message:</span> {item.outreach_message}
              </p>
            )}
            {item.reply_text && (
              <p className="mt-1 text-green-700">
                <span className="font-medium">Their reply:</span> {item.reply_text}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function XOutreachView({ businessId }: { businessId: string }) {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [minScore, setMinScore] = useState<number | undefined>(undefined);

  const { data, isLoading } = useXOutreach(businessId, {
    page,
    status: statusFilter || undefined,
    min_score: minScore,
  });
  const { data: accounts } = useXAccounts(businessId);
  const primaryAccount = accounts?.[0]?.id ?? null;

  const sendDm = useSendXDm(businessId);
  const sendReply = useSendXReply(businessId);
  const update = useUpdateXOutreach(businessId);

  const isSending = sendDm.isPending || sendReply.isPending || update.isPending;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Outreach Queue</h1>
          <p className="text-sm text-slate-500">AI-scored prospects discovered from your X searches</p>
        </div>
        <a href="/x/searches" className="text-sm text-slate-500 hover:text-slate-900">
          Manage searches →
        </a>
      </div>

      {/* Filters */}
      <div className="mb-4 flex gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="dm_sent">DM sent</option>
          <option value="replied">Replied</option>
          <option value="sent">Reply tweet sent</option>
          <option value="skipped">Skipped</option>
        </select>
        <select
          value={minScore ?? ""}
          onChange={(e) => { setMinScore(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">Any score</option>
          <option value="60">Score ≥ 60</option>
          <option value="70">Score ≥ 70</option>
          <option value="80">Score ≥ 80</option>
        </select>
      </div>

      {!primaryAccount && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No X account connected.{" "}
          <a href="/x/connect" className="underline">Connect one</a> to send DMs.
        </div>
      )}

      {(sendDm.isError || sendReply.isError) && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Send failed — X API error. Check your account connection.
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-100 bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2.5 text-left">Prospect</th>
              <th className="px-4 py-2.5 text-left">Followers</th>
              <th className="px-4 py-2.5 text-left">Score</th>
              <th className="px-4 py-2.5 text-left">Status</th>
              <th className="px-4 py-2.5 text-left">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">Loading…</td>
              </tr>
            )}
            {data?.items.map((item) => (
              <OutreachRow
                key={item.id}
                item={item}
                accountId={primaryAccount}
                onSendDm={(id) => primaryAccount && sendDm.mutate({ outreachId: id, accountId: primaryAccount })}
                onSendReply={(id) => primaryAccount && sendReply.mutate({ outreachId: id, accountId: primaryAccount })}
                onSkip={(id) => update.mutate({ outreachId: id, payload: { status: "skipped" } })}
                isSending={isSending}
              />
            ))}
            {!isLoading && data?.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  No prospects yet — run a lead search to find some.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>
            {data.total} total · page {data.page} of {data.pages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded border border-slate-200 px-3 py-1 disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              className="rounded border border-slate-200 px-3 py-1 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
