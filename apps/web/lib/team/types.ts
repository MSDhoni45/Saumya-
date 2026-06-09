export interface TeamMember {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: "business_admin" | "team_member";
  created_at: string;
}

export interface TeamInvite {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  invited_by_name: string | null;
  created_at: string;
}

export interface InviteRequest {
  email: string;
  role: "business_admin" | "team_member";
}

export interface InviteDetails {
  id: string;
  email: string;
  role: string;
  business_name: string;
  invited_by_name: string | null;
  is_valid: boolean;
  expired: boolean;
}

export interface AcceptInviteRequest {
  full_name?: string;
  password?: string;
}

export interface AcceptInviteResponse {
  message: string;
  business_name: string;
  role: string;
}
