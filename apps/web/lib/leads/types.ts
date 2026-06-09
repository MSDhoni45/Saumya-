/**
 * Mirrors `apps/api/app/schemas/leads.py` — keep stage/source literals
 * in sync with the backend's `LeadStage` / `LeadSource` types.
 */

export type LeadStage = "new" | "contacted" | "qualified" | "proposal_sent" | "won" | "lost";
export type LeadSource = "whatsapp" | "manual" | "import" | "referral" | "web";

export type LeadEventType =
  | "lead_created"
  | "stage_changed"
  | "field_updated"
  | "note_added"
  | "note_deleted"
  | "assigned";

export interface Lead {
  id: string;
  business_id: string;
  conversation_id: string | null;
  assigned_user_id: string | null;
  name: string | null;
  phone: string | null;
  email: string | null;
  budget: string | null;
  service_interested: string | null;
  stage: LeadStage;
  source: string;
  notes: string | null;
  stage_changed_at: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedLeads {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LeadUpdatePayload {
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  budget?: string | null;
  service_interested?: string | null;
  stage?: LeadStage;
  assigned_user_id?: string | null;
}

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

export interface LeadNote {
  id: string;
  lead_id: string;
  author_id: string | null;
  content: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Timeline events
// ---------------------------------------------------------------------------

export interface StageChangedPayload {
  from: LeadStage;
  to: LeadStage;
}

export interface FieldUpdatedPayload {
  field: string;
  from: string | null;
  to: string | null;
}

export interface NoteAddedPayload {
  note_id: string;
  preview: string;
}

export interface NoteDeletedPayload {
  content_preview: string;
}

export interface AssignedPayload {
  assigned_to: string | null;
}

export interface LeadCreatedPayload {
  source: string;
}

export interface LeadEvent {
  id: string;
  lead_id: string;
  actor_id: string | null;
  event_type: LeadEventType;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface LeadTimeline {
  events: LeadEvent[];
  notes: LeadNote[];
}

// ---------------------------------------------------------------------------
// List filters (mirrors URL params)
// ---------------------------------------------------------------------------

export interface LeadFilters {
  q: string;
  stage: Set<LeadStage>;
  source: Set<string>;
  assigned: "all" | "me" | "unassigned";
  sort: "updated_desc" | "created_asc" | "stage_asc";
  page: number;
}
