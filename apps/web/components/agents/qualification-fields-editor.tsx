"use client";

import type { QualificationField } from "@/lib/agents/types";

interface Props {
  fields: QualificationField[];
  onChange: (fields: QualificationField[]) => void;
}

export function QualificationFieldsEditor({ fields, onChange }: Props) {
  function addField() {
    onChange([...fields, { key: "", label: "", required: false }]);
  }

  function removeField(index: number) {
    onChange(fields.filter((_, i) => i !== index));
  }

  function updateField(index: number, patch: Partial<QualificationField>) {
    onChange(fields.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  return (
    <div className="space-y-2">
      {fields.map((field, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3">
          <div className="flex-1 grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Key</label>
              <input
                type="text"
                value={field.key}
                onChange={(e) =>
                  updateField(i, {
                    key: e.target.value
                      .toLowerCase()
                      .replace(/\s+/g, "_")
                      .replace(/[^a-z0-9_]/g, ""),
                  })
                }
                placeholder="e.g. budget"
                className="w-full rounded border border-slate-300 px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Label (shown to AI)</label>
              <input
                type="text"
                value={field.label}
                onChange={(e) => updateField(i, { label: e.target.value })}
                placeholder="e.g. Monthly budget"
                className="w-full rounded border border-slate-300 px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
          <div className="flex items-center gap-3 pt-4">
            <label className="flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={field.required}
                onChange={(e) => updateField(i, { required: e.target.checked })}
                className="rounded border-slate-300 text-indigo-600"
              />
              Required
            </label>
            <button
              type="button"
              onClick={() => removeField(i)}
              className="text-slate-400 hover:text-red-500 text-sm"
              aria-label="Remove field"
            >
              ×
            </button>
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={addField}
        className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
      >
        + Add field
      </button>
    </div>
  );
}
