"use client";

import { useState } from "react";
import { useXSearches, useCreateXSearch, useRunXSearch, useDeleteXSearch } from "@/lib/x/queries";

export function XSearchesView({ businessId }: { businessId: string }) {
  const { data: searches, isLoading } = useXSearches(businessId);
  const createSearch = useCreateXSearch(businessId);
  const runSearch = useRunXSearch(businessId);
  const deleteSearch = useDeleteXSearch(businessId);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const [excludeKeywords, setExcludeKeywords] = useState("");
  const [minFollowers, setMinFollowers] = useState(100);
  const [autoDm, setAutoDm] = useState(false);
  const [autoDmThreshold, setAutoDmThreshold] = useState(70);
  const [runQueued, setRunQueued] = useState<string | null>(null);

  function handleCreate() {
    if (!name.trim() || !keywords.trim()) return;
    createSearch.mutate(
      {
        name: name.trim(),
        keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
        exclude_keywords: excludeKeywords.split(",").map((k) => k.trim()).filter(Boolean),
        min_followers: minFollowers,
        language: "en",
        auto_dm_enabled: autoDm,
        auto_dm_threshold: autoDmThreshold,
      },
      {
        onSuccess: () => {
          setName(""); setKeywords(""); setExcludeKeywords("");
          setMinFollowers(100); setAutoDm(false); setShowForm(false);
        },
      },
    );
  }

  function handleRun(searchId: string) {
    runSearch.mutate(searchId, {
      onSuccess: () => setRunQueued(searchId),
    });
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Lead Searches</h1>
          <p className="text-sm text-slate-500">
            Keywords to monitor on X — prospects are scored by AI and added to your outreach queue
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          {showForm ? "Cancel" : "+ New Search"}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Search name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. AI agency prospects"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Keywords (comma-separated)
            </label>
            <input
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="AI automation, social media agency, content marketing"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Exclude keywords (comma-separated, optional)
            </label>
            <input
              value={excludeKeywords}
              onChange={(e) => setExcludeKeywords(e.target.value)}
              placeholder="spam, crypto, nft"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
          <div className="flex gap-4 items-end">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Min followers
              </label>
              <input
                type="number"
                value={minFollowers}
                onChange={(e) => setMinFollowers(Number(e.target.value))}
                min={0}
                className="w-28 rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input
                type="checkbox"
                id="auto-dm"
                checked={autoDm}
                onChange={(e) => setAutoDm(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              <label htmlFor="auto-dm" className="text-sm text-slate-700">Auto-DM enabled</label>
            </div>
            {autoDm && (
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Min score for auto-DM
                </label>
                <input
                  type="number"
                  value={autoDmThreshold}
                  onChange={(e) => setAutoDmThreshold(Number(e.target.value))}
                  min={0} max={100}
                  className="w-20 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </div>
            )}
          </div>
          <button
            onClick={handleCreate}
            disabled={createSearch.isPending || !name.trim() || !keywords.trim()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {createSearch.isPending ? "Creating…" : "Create Search"}
          </button>
        </div>
      )}

      {/* Search list */}
      <div className="space-y-3">
        {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {searches?.map((search) => (
          <div key={search.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-slate-900">{search.name}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {search.keywords.map((kw) => (
                    <span key={kw} className="rounded-full bg-violet-50 px-2 py-0.5 text-xs text-violet-700">
                      {kw}
                    </span>
                  ))}
                  {search.exclude_keywords.map((kw) => (
                    <span key={kw} className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-500">
                      -{kw}
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Min {search.min_followers.toLocaleString()} followers · {search.language.toUpperCase()}
                  {search.auto_dm_enabled && (
                    <span className="ml-2 text-violet-600">
                      · Auto-DM on (score ≥ {search.auto_dm_threshold})
                    </span>
                  )}
                </p>
                {search.last_run_at && (
                  <p className="text-xs text-slate-400">
                    Last run: {new Date(search.last_run_at).toLocaleString()}
                  </p>
                )}
                {runQueued === search.id && (
                  <p className="text-xs text-green-600 mt-1">Queued — results appear in Outreach shortly.</p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${search.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                  {search.is_active ? "Active" : "Inactive"}
                </span>
                <button
                  onClick={() => handleRun(search.id)}
                  disabled={runSearch.isPending}
                  className="rounded border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Run Now
                </button>
                <button
                  onClick={() => deleteSearch.mutate(search.id)}
                  disabled={deleteSearch.isPending}
                  className="text-xs text-red-400 hover:text-red-600 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
        {!isLoading && searches?.length === 0 && (
          <p className="text-center text-sm text-slate-400 py-8">
            No searches yet. Create one to start finding leads on X.
          </p>
        )}
      </div>
    </div>
  );
}
