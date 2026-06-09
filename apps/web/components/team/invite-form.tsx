"use client";

import { useState } from "react";

import { useCreateInvite } from "@/lib/team/queries";

interface Props {
  businessId: string;
}

export function InviteForm({ businessId }: Props) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"team_member" | "business_admin">("team_member");
  const [success, setSuccess] = useState(false);

  const createInvite = useCreateInvite(businessId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;

    createInvite.mutate(
      { email: email.trim(), role },
      {
        onSuccess: () => {
          setEmail("");
          setRole("team_member");
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
        },
      },
    );
  }

  const error =
    createInvite.error instanceof Error ? createInvite.error.message : null;

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="colleague@example.com"
          required
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as typeof role)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="team_member">Team Member</option>
          <option value="business_admin">Admin</option>
        </select>
        <button
          type="submit"
          disabled={createInvite.isPending || !email.trim()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {createInvite.isPending ? "Sending…" : "Invite"}
        </button>
      </div>

      {success && (
        <p className="text-sm text-green-600">Invitation sent!</p>
      )}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </form>
  );
}
