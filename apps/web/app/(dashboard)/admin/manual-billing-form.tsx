"use client";

import { useState } from "react";

import { ApiError, api } from "@/lib/api/client";

type Mode = "activate" | "deactivate";

interface SubscriptionResponse {
  plan: string;
  status: string;
  current_period_end: string | null;
}

const PLANS = ["starter", "growth", "agency", "free"] as const;

export function ManualBillingForm() {
  const [businessId, setBusinessId] = useState("");
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
      <div className="space-y-1">
        <label htmlFor="business_id" className="block text-sm font-medium text-slate-900">
          Business ID
        </label>
        <input
          id="business_id"
          type="text"
          value={businessId}
          onChange={(e) => setBusinessId(e.target.value)}
          placeholder="00000000-0000-0000-0000-000000000000"
          className="w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm focus:border-brand-500 focus:outline-none"
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
