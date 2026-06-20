"use client";

import { useState } from "react";
import { useXPosts, useXAccounts, useCreateXPost, usePublishXPost, useDeleteXPost } from "@/lib/x/queries";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600",
  scheduled: "bg-blue-100 text-blue-700",
  posted: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-600",
};

export function XPostsView({ businessId }: { businessId: string }) {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading } = useXPosts(businessId, page, statusFilter || undefined);
  const { data: accounts } = useXAccounts(businessId);

  const createPost = useCreateXPost(businessId);
  const publishPost = usePublishXPost(businessId);
  const deletePost = useDeleteXPost(businessId);

  const [content, setContent] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const primaryAccountId = accounts?.[0]?.id ?? "";

  function handleCreate() {
    if (!content.trim() || !primaryAccountId) return;
    createPost.mutate(
      {
        x_account_id: primaryAccountId,
        content: content.trim(),
        scheduled_at: scheduledAt || undefined,
      },
      {
        onSuccess: () => {
          setContent("");
          setScheduledAt("");
          setShowForm(false);
        },
      },
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Posts</h1>
          <p className="text-sm text-slate-500">Schedule tweets and threads for Influnexus</p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          {showForm ? "Cancel" : "+ New Post"}
        </button>
      </div>

      {/* New post form */}
      {showForm && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5">
          {!primaryAccountId && (
            <p className="mb-3 text-sm text-amber-600">
              No X account connected. <a href="/x/connect" className="underline">Connect one first.</a>
            </p>
          )}
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            maxLength={280}
            rows={4}
            placeholder="What's happening? (280 chars)"
            className="w-full rounded-lg border border-slate-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
          />
          <p className="mt-1 text-right text-xs text-slate-400">{content.length}/280</p>
          <div className="mt-3 flex items-center gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                Schedule at (optional)
              </label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
            <div className="mt-4">
              <button
                onClick={handleCreate}
                disabled={createPost.isPending || !content.trim() || !primaryAccountId}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
              >
                {scheduledAt ? "Schedule" : "Save Draft"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="mb-4">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">All posts</option>
          <option value="draft">Draft</option>
          <option value="scheduled">Scheduled</option>
          <option value="posted">Posted</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <div className="space-y-3">
        {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {data?.items.map((post) => (
          <div key={post.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-4">
              <p className="text-sm text-slate-800 flex-1">{post.content}</p>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[post.status]}`}>
                {post.status}
              </span>
            </div>
            <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
              {post.scheduled_at && (
                <span>Scheduled: {new Date(post.scheduled_at).toLocaleString()}</span>
              )}
              {post.posted_at && (
                <span>Posted: {new Date(post.posted_at).toLocaleString()}</span>
              )}
              {post.tweet_ids.length > 0 && (
                <a
                  href={`https://twitter.com/i/web/status/${post.tweet_ids[0]}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline"
                >
                  View on X ↗
                </a>
              )}
              <div className="ml-auto flex gap-2">
                {(post.status === "draft" || post.status === "scheduled") && (
                  <button
                    onClick={() => publishPost.mutate(post.id)}
                    disabled={publishPost.isPending}
                    className="rounded bg-violet-600 px-2.5 py-1 text-white hover:bg-violet-700 disabled:opacity-50"
                  >
                    Publish Now
                  </button>
                )}
                {post.status !== "posted" && (
                  <button
                    onClick={() => deletePost.mutate(post.id)}
                    disabled={deletePost.isPending}
                    className="rounded border border-slate-200 px-2.5 py-1 text-red-500 hover:bg-red-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
            {post.error_message && (
              <p className="mt-2 text-xs text-red-500">{post.error_message}</p>
            )}
          </div>
        ))}
        {!isLoading && data?.items.length === 0 && (
          <p className="text-center text-sm text-slate-400 py-8">No posts yet. Create one above.</p>
        )}
      </div>

      {data && data.pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>Page {data.page} of {data.pages}</span>
          <div className="flex gap-2">
            <button onClick={() => setPage((p) => p - 1)} disabled={page === 1} className="rounded border border-slate-200 px-3 py-1 disabled:opacity-40">← Prev</button>
            <button onClick={() => setPage((p) => p + 1)} disabled={page === data.pages} className="rounded border border-slate-200 px-3 py-1 disabled:opacity-40">Next →</button>
          </div>
        </div>
      )}
    </div>
  );
}
