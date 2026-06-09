import type { Lead, LeadEvent, LeadStage } from "@/lib/leads/types";

// ---------------------------------------------------------------------------
// Stage display
// ---------------------------------------------------------------------------

export const STAGE_ORDER: LeadStage[] = [
  "new",
  "contacted",
  "qualified",
  "proposal_sent",
  "won",
  "lost",
];

interface StageStyle {
  label: string;
  dot: string;
  text: string;
  bg: string;
  border: string;
}

export const STAGE_STYLES: Record<LeadStage, StageStyle> = {
  new: {
    label: "New",
    dot: "bg-slate-400",
    text: "text-slate-600",
    bg: "bg-slate-100",
    border: "border-slate-200",
  },
  contacted: {
    label: "Contacted",
    dot: "bg-blue-400",
    text: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-200",
  },
  qualified: {
    label: "Qualified",
    dot: "bg-violet-500",
    text: "text-violet-700",
    bg: "bg-violet-50",
    border: "border-violet-200",
  },
  proposal_sent: {
    label: "Proposal sent",
    dot: "bg-amber-500",
    text: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
  },
  won: {
    label: "Won",
    dot: "bg-emerald-500",
    text: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
  },
  lost: {
    label: "Lost",
    dot: "bg-red-400",
    text: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-200",
  },
};

export function stageStyle(stage: string): StageStyle {
  return STAGE_STYLES[stage as LeadStage] ?? STAGE_STYLES.new;
}

// ---------------------------------------------------------------------------
// Source display
// ---------------------------------------------------------------------------

const SOURCE_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  manual: "Manual",
  import: "Import",
  referral: "Referral",
  web: "Web",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

// ---------------------------------------------------------------------------
// Lead display name
// ---------------------------------------------------------------------------

export function leadDisplayName(lead: Pick<Lead, "name" | "phone" | "email">): string {
  if (lead.name?.trim()) return lead.name.trim();
  if (lead.phone) return lead.phone;
  if (lead.email) return lead.email;
  return "Unknown lead";
}

export function leadInitials(lead: Pick<Lead, "name" | "phone" | "email">): string {
  const name = lead.name?.trim();
  if (name) {
    const [first, second] = name.split(/\s+/).filter(Boolean);
    if (first && second) return (first.charAt(0) + second.charAt(0)).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }
  if (lead.phone) return lead.phone.slice(-2);
  if (lead.email) return lead.email.slice(0, 2).toUpperCase();
  return "??";
}

// ---------------------------------------------------------------------------
// Timeline event → human-readable summary
// ---------------------------------------------------------------------------

export function timelineEventSummary(event: LeadEvent): string {
  const payload = event.payload as Record<string, string | null>;
  switch (event.event_type) {
    case "lead_created":
      return `Lead created from ${payload.source ?? "unknown source"}`;
    case "stage_changed":
      return `Stage changed from ${stageStyle(payload.from ?? "").label} to ${stageStyle(payload.to ?? "").label}`;
    case "field_updated": {
      const label = FIELD_LABELS[payload.field ?? ""] ?? payload.field ?? "field";
      if (!payload.from) return `${label} set to "${payload.to}"`;
      if (!payload.to) return `${label} cleared`;
      return `${label} changed from "${payload.from}" to "${payload.to}"`;
    }
    case "note_added":
      return "Note added";
    case "note_deleted":
      return "Note deleted";
    case "assigned":
      return payload.assigned_to ? "Lead assigned" : "Assignment cleared";
    default:
      return (event.event_type as string).replace(/_/g, " ");
  }
}

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  phone: "Phone",
  email: "Email",
  budget: "Budget",
  service_interested: "Service interest",
};
