"use client";

import { useEffect } from "react";
import { useXAccounts, useXAuthorizeUrl, useDisconnectXAccount } from "@/lib/x/queries";

const ERROR_MESSAGES: Record<string, string> = {
  token_exchange_failed: "X rejected the authorization — please try again.",
  profile_fetch_failed: "Connected but couldn't fetch your X profile. Try reconnecting.",
  missing_params: "Invalid callback — please try again.",
  access_denied: "You cancelled the authorization.",
};

export function XConnectView({
  businessId,
  connected,
  username,
  error,
}: {
  businessId: string;
  connected: boolean;
  username?: string;
  error?: string;
}) {
  const { data: accounts, isLoading, refetch } = useXAccounts(businessId);
  const authorize = useXAuthorizeUrl(businessId);
  const disconnect = useDisconnectXAccount(businessId);

  useEffect(() => {
    if (connected) refetch();
  }, [connected, refetch]);

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900">Connect X Account</h1>
      <p className="mt-1 text-sm text-slate-500">
        Link your X (Twitter) account to enable posting, lead discovery, and AI-powered outreach.
      </p>

      {/* Success / error banners */}
      {connected && username && (
        <div className="mt-6 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          @{username} connected successfully.
        </div>
      )}
      {error && (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {ERROR_MESSAGES[error] ?? `Error: ${error}`}
        </div>
      )}

      {/* Connected accounts */}
      <div className="mt-8 space-y-3">
        {isLoading && (
          <p className="text-sm text-slate-400">Loading connected accounts…</p>
        )}
        {accounts?.map((account) => (
          <div
            key={account.id}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3"
          >
            <div>
              <p className="font-medium text-slate-900">@{account.username}</p>
              {account.display_name && (
                <p className="text-xs text-slate-500">{account.display_name}</p>
              )}
              <span
                className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                  account.is_active
                    ? "bg-green-100 text-green-700"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {account.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            <button
              onClick={() => disconnect.mutate(account.id)}
              disabled={disconnect.isPending}
              className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50"
            >
              Disconnect
            </button>
          </div>
        ))}
        {accounts?.length === 0 && !isLoading && (
          <p className="text-sm text-slate-400">No accounts connected yet.</p>
        )}
      </div>

      {/* Connect button */}
      <div className="mt-6">
        <button
          onClick={() => authorize.mutate()}
          disabled={authorize.isPending}
          className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {authorize.isPending ? "Redirecting to X…" : "+ Connect X Account"}
        </button>
        {authorize.isError && (
          <p className="mt-2 text-xs text-red-500">
            {(authorize.error as Error).message}
          </p>
        )}
      </div>

      {/* Nav links */}
      <div className="mt-10 flex gap-4 text-sm text-slate-500">
        <a href="/x" className="hover:text-slate-900">← Dashboard</a>
        <a href="/x/outreach" className="hover:text-slate-900">Outreach →</a>
      </div>
    </div>
  );
}
