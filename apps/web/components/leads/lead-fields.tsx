"use client";

import { useRef, useState } from "react";

import type { Lead, LeadUpdatePayload } from "@/lib/leads/types";

type FieldKey = "name" | "phone" | "email" | "budget" | "service_interested";

const FIELD_META: { key: FieldKey; label: string; placeholder: string }[] = [
  { key: "name", label: "Name", placeholder: "Full name" },
  { key: "phone", label: "Phone", placeholder: "+1 415 555 0100" },
  { key: "email", label: "Email", placeholder: "name@example.com" },
  { key: "budget", label: "Budget", placeholder: "e.g. $5,000–$10,000" },
  { key: "service_interested", label: "Service interest", placeholder: "e.g. Premium subscription" },
];

export function LeadFields({
  lead,
  onSave,
  isSaving,
}: {
  lead: Lead;
  onSave: (payload: LeadUpdatePayload) => void;
  isSaving: boolean;
}) {
  return (
    <div className="divide-y divide-slate-100">
      {FIELD_META.map(({ key, label, placeholder }) => (
        <InlineField
          key={key}
          label={label}
          value={lead[key] ?? ""}
          placeholder={placeholder}
          isSaving={isSaving}
          onSave={(value) => onSave({ [key]: value || null })}
        />
      ))}
    </div>
  );
}

function InlineField({
  label,
  value,
  placeholder,
  isSaving,
  onSave,
}: {
  label: string;
  value: string;
  placeholder: string;
  isSaving: boolean;
  onSave: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = () => {
    setDraft(value);
    setEditing(true);
    // Focus after state flush
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const commit = () => {
    setEditing(false);
    if (draft.trim() !== value.trim()) {
      onSave(draft.trim());
    }
  };

  const cancel = () => {
    setEditing(false);
    setDraft(value);
  };

  return (
    <div className="flex items-start gap-3 py-2.5 pr-3">
      <span className="w-32 shrink-0 pt-0.5 text-xs font-medium text-slate-500">{label}</span>
      {editing ? (
        <div className="flex flex-1 items-center gap-1.5">
          <input
            ref={inputRef}
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") cancel();
            }}
            placeholder={placeholder}
            disabled={isSaving}
            className="flex-1 rounded border border-brand-400 px-2 py-1 text-sm text-slate-900 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={startEdit}
          className="flex-1 rounded px-1 text-left text-sm text-slate-800 hover:bg-slate-100"
          title="Click to edit"
        >
          {value || <span className="text-slate-400">{placeholder}</span>}
        </button>
      )}
    </div>
  );
}
