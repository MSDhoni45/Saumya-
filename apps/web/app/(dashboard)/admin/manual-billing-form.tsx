"use client";

import { useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api/client";

type Mode = "activate" | "deactivate";

interface SubscriptionResponse {
  plan: string;
  status: string;
  current_period_end: string | null;
}

interface BusinessListItem {
  id: string;
  name: string;
  industry: string | null;
  plan: string;
  status: string;
  created_at: string;
}

const PLANS = ["starter", "growth", "agency", "free"] as const;

export function ManualBillingForm() {
  const [businessId, setBusinessId] = useState("");
  const [businesses, setBusinesses] = useState<BusinessListItem[]>([]);
  const [search, setSearch] = useState("");
  const [loadingList, setLoadingList] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoadingList(true);
      try {
        const qs = search.trim() ? `?q=${encodeURIComponent(search.trim())}` : "";
        const list = await api.get<BusinessListItem[]>(`/admin/businesses${qs}`);
        if (!cancelled) setBusinesses(list);
      } catch {
        // Silent — operator can still paste a UUID directly.
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [search]);
  const [plan, setPlan] = useState<(typeof PLANS)[number]>("starter");
  const [periodDays, setPeriodDays] = useState(30);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<Mode | null>(null);
  const [result, setResult] = useState<SubscriptionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (mode: Mode) => {
    setError(null);
    setResult(null);
    setBusy(mode);
    try {
      const path =
        mode === "activate"
          ? `/admin/businesses/${businessId}/activate`
          : `/admin/businesses/${businessId}/deactivate`;
      const body =
        mode === "activate"
          ? { plan, period_days: periodDays, note: note || null }
          : undefined;
      const sub = await api.post<SubscriptionResponse>(path, body);
      setResult(sub);
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | string | null;
        const detail =
          typeof body === "string"
            ? body
            : body && typeof body === "object" && "detail" in body
              ? body.detail
              : null;
        setError(`HTTP ${err.status}${detail ? ` — ${detail}` : ""}`);
      } else {
        setError(String(err));
      }
    } finally {
      setBusy(null);
    }
  };

  const canSubmit = businessId.trim().length >= 8 && !busy;

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div className="space-y-2">
        <label htmlFor="business_search" className="block text-sm font-medium text-slate-900">
          Business
        </label>
        <input
          id="business_search"
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name…"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          autoComplete="off"
        />
        <div className="max-h-48 overflow-y-auto rounded border border-slate-200">
          {loadingList && businesses.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">Loading…</p>
          ) : businesses.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">No matches.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {businesses.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => setBusinessId(b.id)}
                    className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                      businessId === b.id ? "bg-brand-50" : ""
                    }`}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      <span className="font-medium text-slate-900">{b.name}</span>
                      {b.industry && (
                        <span className="ml-2 text-xs text-slate-500">{b.industry}</span>
                      )}
                    </span>
                    <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                      {b.plan} · {b.status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <input
          id="business_id"
          type="text"
          value={businessId}
          onChange={(e) => setBusinessId(e.target.value)}
          placeholder="…or paste business UUID"
          className="w-full rounded border border-slate-300 px-3 py-2 font-mono text-xs focus:border-brand-500 focus:outline-none"
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label htmlFor="plan" className="block text-sm font-medium text-slate-900">
            Plan
          </label>
          <select
            id="plan"
            value={plan}
            onChange={(e) => setPlan(e.target.value as (typeof PLANS)[number])}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          >
            {PLANS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="period_days" className="block text-sm font-medium text-slate-900">
            Period (days)
          </label>
          <input
            id="period_days"
            type="number"
            min={1}
            max={400}
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>
      </div>

      <div className="space-y-1">
        <label htmlFor="note" className="block text-sm font-medium text-slate-900">
          Note (optional — written into billing_events)
        </label>
        <input
          id="note"
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="UPI ref 1234 — invoice INV-007"
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => submit("activate")}
          className="rounded bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "activate" ? "Activating…" : "Activate plan"}
        </button>
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => submit("deactivate")}
          className="rounded border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "deactivate" ? "Reverting…" : "Revert to free"}
        </button>
      </div>

      {error && (
        <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {result && (
        <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          <p>
            <span className="font-semibold">{result.plan}</span> · status {result.status}
            {result.current_period_end ? ` · until ${result.current_period_end}` : ""}
          </p>
        </div>
      )}
    </section>
  );
}
