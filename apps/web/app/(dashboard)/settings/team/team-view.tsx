"use client";

import { InviteForm } from "@/components/team/invite-form";
import { MemberRow } from "@/components/team/member-row";
import { PendingInvites } from "@/components/team/pending-invites";
import { hasRole } from "@/lib/auth/rbac";
import type { UserRole } from "@/lib/auth/rbac";
import { useMembers } from "@/lib/team/queries";

interface Props {
  businessId: string;
  currentUserId: string;
  currentRole: UserRole;
}

export function TeamView({ businessId, currentUserId, currentRole }: Props) {
  const { data: members, isLoading } = useMembers(businessId);
  const isAdmin = hasRole({ role: currentRole }, "business_admin");

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 py-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Team</h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage the people who have access to your WhatsAgent workspace.
        </p>
      </div>

      {/* Members list */}
      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-6 py-4">
          <h2 className="text-sm font-semibold text-slate-900">Members</h2>
        </div>
        <div className="divide-y divide-slate-100 px-6">
          {isLoading ? (
            <p className="py-4 text-sm text-slate-400">Loading…</p>
          ) : members && members.length > 0 ? (
            members.map((member) => (
              <MemberRow
                key={member.id}
                member={member}
                currentUserId={currentUserId}
                isAdmin={isAdmin}
                businessId={businessId}
              />
            ))
          ) : (
            <p className="py-4 text-sm text-slate-400">No members found.</p>
          )}
        </div>
      </section>

      {/* Invite section — admins only */}
      {isAdmin && (
        <>
          <section className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-6 py-4">
              <h2 className="text-sm font-semibold text-slate-900">Invite someone</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                They&apos;ll receive an email with a link to join your workspace.
              </p>
            </div>
            <div className="px-6 py-4">
              <InviteForm businessId={businessId} />
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-6 py-4">
              <h2 className="text-sm font-semibold text-slate-900">Pending invitations</h2>
            </div>
            <div className="px-6 py-2">
              <PendingInvites businessId={businessId} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
