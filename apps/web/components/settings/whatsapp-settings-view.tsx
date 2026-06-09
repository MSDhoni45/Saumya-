"use client";

import { useState } from "react";
import { toast } from "sonner";

import {
  useConnectWhatsApp,
  useDisconnectWhatsApp,
  useWhatsAppAccounts,
} from "@/lib/inbox/queries";
import type { UserRole } from "@/lib/auth/rbac";
import type { WhatsAppAccount } from "@/lib/inbox/types";

export function WhatsAppSettingsView({
  businessId,
  userRole,
}: {
  businessId: string;
  userRole: UserRole;
}) {
  const accountsQuery = useWhatsAppAccounts(businessId);
  const accounts = accountsQuery.data ?? [];
  const canManage = userRole === "business_admin" || userRole === "super_admin";

  return (
    <div className="space-y-6">
      {accountsQuery.isLoading ? (
        <AccountsSkeleton />
      ) : accountsQuery.isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load WhatsApp accounts.{" "}
          <button
            type="button"
            className="font-medium underline underline-offset-2"
            onClick={() => accountsQuery.refetch()}
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          {accounts.length === 0 ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center">
              <p className="text-sm font-medium text-slate-700">No WhatsApp numbers connected</p>
              <p className="mt-1 text-sm text-slate-500">
                Connect a WhatsApp Business number to start receiving messages.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
              {accounts.map((account) => (
                <AccountRow
                  key={account.id}
                  account={account}
                  businessId={businessId}
                  canManage={canManage}
                />
              ))}
            </div>
          )}
        </>
      )}

      {canManage && <ConnectAccountForm businessId={businessId} />}
    </div>
  );
}

function AccountRow({
  account,
  businessId,
  canManage,
}: {
  account: WhatsAppAccount;
  businessId: string;
  canManage: boolean;
}) {
  const disconnect = useDisconnectWhatsApp(businessId);

  const handleDisconnect = () => {
    disconnect.mutate(account.id, {
      onSuccess: () => toast.success(`Disconnected ${account.display_name ?? account.phone_number}`),
      onError: () => toast.error("Failed to disconnect the account."),
    });
  };

  const statusColor: Record<WhatsAppAccount["status"], string> = {
    connected: "bg-emerald-500",
    pending: "bg-amber-500",
    disconnected: "bg-slate-400",
    error: "bg-red-500",
  };

  const statusLabel: Record<WhatsAppAccount["status"], string> = {
    connected: "Connected",
    pending: "Pending",
    disconnected: "Disconnected",
    error: "Error",
  };

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-4">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-900">
          {account.display_name ?? account.phone_number}
        </p>
        <p className="mt-0.5 text-xs text-slate-500">{account.phone_number}</p>
        {account.connected_at && (
          <p className="mt-0.5 text-xs text-slate-400">
            Connected {new Date(account.connected_at).toLocaleDateString()}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className={`flex items-center gap-1.5 text-xs font-medium ${account.status === "connected" ? "text-emerald-700" : "text-slate-500"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${statusColor[account.status]}`} aria-hidden />
          {statusLabel[account.status]}
        </span>
        {canManage && account.status === "connected" && (
          <button
            type="button"
            onClick={handleDisconnect}
            disabled={disconnect.isPending}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-red-300 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {disconnect.isPending ? "Disconnecting…" : "Disconnect"}
          </button>
        )}
      </div>
    </div>
  );
}

const EMPTY_FORM = { waba_id: "", phone_number_id: "", access_token: "", display_name: "" };

function ConnectAccountForm({ businessId }: { businessId: string }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const connect = useConnectWhatsApp(businessId);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.waba_id || !form.phone_number_id || !form.access_token) return;
    connect.mutate(
      {
        waba_id: form.waba_id.trim(),
        phone_number_id: form.phone_number_id.trim(),
        access_token: form.access_token.trim(),
        display_name: form.display_name.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("WhatsApp account connected.");
          setForm(EMPTY_FORM);
          setOpen(false);
        },
        onError: () => toast.error("Failed to connect. Check your credentials and try again."),
      },
    );
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full rounded-lg border border-dashed border-slate-300 px-4 py-3 text-sm font-medium text-slate-600 transition hover:border-slate-400 hover:text-slate-800"
      >
        + Connect a WhatsApp Business number
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-4 text-sm font-semibold text-slate-900">Connect WhatsApp Business number</h2>
      <div className="space-y-3">
        <Field
          label="WhatsApp Business Account ID (WABA ID)"
          value={form.waba_id}
          onChange={(v) => setForm((f) => ({ ...f, waba_id: v }))}
          placeholder="123456789012345"
          required
        />
        <Field
          label="Phone Number ID"
          value={form.phone_number_id}
          onChange={(v) => setForm((f) => ({ ...f, phone_number_id: v }))}
          placeholder="123456789012345"
          required
        />
        <Field
          label="Permanent / System-user Access Token"
          value={form.access_token}
          onChange={(v) => setForm((f) => ({ ...f, access_token: v }))}
          placeholder="EAAxxxxxx…"
          required
          type="password"
        />
        <Field
          label="Display name (optional)"
          value={form.display_name}
          onChange={(v) => setForm((f) => ({ ...f, display_name: v }))}
          placeholder="Sales hotline"
        />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setForm(EMPTY_FORM);
          }}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:border-slate-300"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={connect.isPending || !form.waba_id || !form.phone_number_id || !form.access_token}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {connect.isPending ? "Connecting…" : "Connect"}
        </button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  type?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
    </div>
  );
}

function AccountsSkeleton() {
  return (
    <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-4">
          <div className="flex-1 space-y-2">
            <div className="h-3.5 w-40 animate-pulse rounded bg-slate-200" />
            <div className="h-2.5 w-24 animate-pulse rounded bg-slate-100" />
          </div>
          <div className="h-5 w-20 animate-pulse rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
