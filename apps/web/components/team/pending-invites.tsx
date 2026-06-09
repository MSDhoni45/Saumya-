"use client";

import { useInvites, useRevokeInvite } from "@/lib/team/queries";
import type { TeamInvite } from "@/lib/team/types";

interface Props {
  businessId: string;
}

function InviteRow({
  invite,
  businessId,
}: {
  invite: TeamInvite;
  businessId: string;
}) {
  const revoke = useRevokeInvite(businessId);
  const expiresAt = new Date(invite.expires_at).toLocaleDateString();

  return (
    <div className="flex items-center justify-between py-2.5">
      <div>
        <p className="text-sm font-medium text-slate-900">{invite.email}</p>
        <p className="text-xs text-slate-500">
          {invite.role === "business_admin" ? "Admin" : "Team Member"} · expires {expiresAt}
        </p>
      </div>
      <button
        onClick={() => revoke.mutate(invite.id)}
        disabled={revoke.isPending}
        className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-50"
      >
        Revoke
      </button>
    </div>
  );
}

export function PendingInvites({ businessId }: Props) {
  const { data: invites, isLoading } = useInvites(businessId);

  if (isLoading) {
    return <p className="text-sm text-slate-400">Loading…</p>;
  }

  if (!invites || invites.length === 0) {
    return <p className="text-sm text-slate-400">No pending invitations.</p>;
  }

  return (
    <div className="divide-y divide-slate-100">
      {invites.map((invite) => (
        <InviteRow key={invite.id} invite={invite} businessId={businessId} />
      ))}
    </div>
  );
}
