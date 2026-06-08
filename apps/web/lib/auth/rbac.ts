/**
 * Mirrors `apps/api/app/schemas/auth.py::UserRole` and the
 * `users_role_check` constraint (migration 20260608140002). Keep in sync —
 * this is the single source of truth for role names on the frontend.
 */
export type UserRole = "super_admin" | "business_admin" | "team_member";

export interface SessionUser {
  id: string;
  business_id: string | null;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: UserRole;
  created_at: string;
}

export interface BusinessSummary {
  id: string;
  name: string;
  industry: string | null;
  timezone: string;
}

export interface MeResponse {
  user: SessionUser;
  business: BusinessSummary | null;
}

const ROLE_RANK: Record<UserRole, number> = {
  team_member: 0,
  business_admin: 1,
  super_admin: 2,
};

/**
 * `super_admin` is treated as a superset of `business_admin` (platform
 * operators must be able to act on any tenant's behalf for support and
 * moderation) — mirrors `require_roles` in app/api/deps.py on the backend.
 */
export function hasRole(user: Pick<SessionUser, "role">, ...allowed: UserRole[]): boolean {
  if (allowed.includes(user.role)) return true;
  if (user.role === "super_admin" && allowed.includes("business_admin")) return true;
  return false;
}

export function roleLabel(role: UserRole): string {
  switch (role) {
    case "super_admin":
      return "Super Admin";
    case "business_admin":
      return "Business Admin";
    case "team_member":
      return "Team Member";
  }
}

export function roleAtLeast(user: Pick<SessionUser, "role">, minimum: UserRole): boolean {
  return ROLE_RANK[user.role] >= ROLE_RANK[minimum];
}
