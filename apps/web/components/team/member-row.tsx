"use client";

import { useState } from "react";

import { useChangeRole, useRemoveMember } from "@/lib/team/queries";
import type { TeamMember } from "@/lib/team/types";

interface Props {
  member: TeamMember;
  currentUserId: string;
  isAdmin: boolean;
  businessId: string;
}

const ROLE_LABELS: Record<string, string> = {
  business_admin: "Admin",
  team_member: "Team Member",
};

export function MemberRow({ member, currentUserId, isAdmin, businessId }: Props) {
  const [confirmRemove, setConfirmRemove] = useState(false);
  const removeMutation = useRemoveMember(businessId);
  const changeRoleMutation = useChangeRole(businessId);

  const isSelf = member.id === currentUserId;
  const initials = member.full_name
    ? member.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : member.email[0].toUpperCase();

  function handleRoleToggle() {
    const newRole = member.role === "business_admin" ? "team_member" : "business_admin";
    changeRoleMutation.mutate({ userId: member.id, role: newRole });
  }

  function handleRemove() {
    if (!confirmRemove) {
      setConfirmRemove(true);
      return;
    }
    removeMutation.mutate(member.id, {
      onSettled: () => setConfirmRemove(false),
    });
  }

  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
          {initials}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-900">
            {member.full_name ?? member.email}
            {isSelf && <span className="ml-2 text-xs text-slate-400">(you)</span>}
          </p>
          {member.full_name && (
            <p className="text-xs text-slate-500">{member.email}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            member.role === "business_admin"
              ? "bg-indigo-50 text-indigo-700"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {ROLE_LABELS[member.role] ?? member.role}
        </span>

        {isAdmin && !isSelf && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleRoleToggle}
              disabled={changeRoleMutation.isPending}
              className="text-xs text-slate-500 hover:text-slate-700 disabled:opacity-50"
            >
              {member.role === "business_admin" ? "Make member" : "Make admin"}
            </button>

            {confirmRemove ? (
              <div className="flex items-center gap-1">
                <button
                  onClick={handleRemove}
                  disabled={removeMutation.isPending}
                  className="text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmRemove(false)}
                  className="text-xs text-slate-400 hover:text-slate-600"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={handleRemove}
                className="text-xs text-slate-400 hover:text-red-600"
              >
                Remove
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
