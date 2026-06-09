"use client";

import { useState } from "react";

import { QualificationFieldsEditor } from "./qualification-fields-editor";
import type { AiAgent, CreateAgentRequest, QualificationField } from "@/lib/agents/types";

const MODELS: Record<"openai" | "anthropic", { value: string; label: string }[]> = {
  openai: [
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  ],
  anthropic: [
    { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
    { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
    { value: "claude-opus-4-8", label: "Claude Opus 4.8" },
  ],
};

const DEFAULT_PERSONA =
  "You are a friendly, knowledgeable sales assistant. Be concise, helpful, and never invent facts about the business.";

interface Props {
  initial?: AiAgent;
  onSave: (data: CreateAgentRequest) => Promise<void>;
  saving: boolean;
  saveLabel?: string;
}

export function AgentForm({ initial, onSave, saving, saveLabel = "Save agent" }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [agentType, setAgentType] = useState<"sales" | "support" | "follow_up">(
    initial?.agent_type ?? "sales",
  );
  const [provider, setProvider] = useState<"openai" | "anthropic">(
    initial?.provider ?? "openai",
  );
  const [model, setModel] = useState(initial?.model ?? "gpt-4o-mini");
  const [temperature, setTemperature] = useState(initial?.temperature ?? 0.4);
  const [persona, setPersona] = useState(initial?.persona ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [qualFields, setQualFields] = useState<QualificationField[]>(
    (initial?.qualification_fields as QualificationField[]) ?? [],
  );
  const [error, setError] = useState<string | null>(null);

  function handleProviderChange(p: "openai" | "anthropic") {
    setProvider(p);
    setModel(MODELS[p][0].value);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Agent name is required.");
      return;
    }
    try {
      await onSave({
        name: name.trim(),
        agent_type: agentType,
        persona: persona.trim() || undefined,
        provider,
        model,
        temperature,
        qualification_fields: qualFields.filter((f) => f.key && f.label),
        is_active: isActive,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save agent.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic info */}
      <section className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Agent name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sales Assistant"
              required
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Agent type</label>
            <select
              value={agentType}
              onChange={(e) => setAgentType(e.target.value as typeof agentType)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="sales">Sales</option>
              <option value="support">Support</option>
              <option value="follow_up">Follow-up</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3">
          <div>
            <p className="text-sm font-medium text-slate-900">Active</p>
            <p className="text-xs text-slate-500">
              Inactive agents won't reply to new messages
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsActive(!isActive)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isActive ? "bg-indigo-600" : "bg-slate-300"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                isActive ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </section>

      {/* LLM config */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-900">AI Model</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Provider</label>
            <select
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value as typeof provider)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {MODELS[provider].map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Temperature: {temperature.toFixed(1)}
            </label>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-indigo-600"
            />
            <div className="flex justify-between text-xs text-slate-400">
              <span>Precise</span>
              <span>Creative</span>
            </div>
          </div>
        </div>
      </section>

      {/* Persona */}
      <section className="space-y-2">
        <div>
          <label className="block text-sm font-semibold text-slate-900 mb-1">Persona / System prompt</label>
          <p className="text-xs text-slate-500 mb-2">
            Describe who the agent is, how it should behave, and what it should know about your business.
          </p>
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            placeholder={DEFAULT_PERSONA}
            rows={6}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
          />
        </div>
      </section>

      {/* Qualification fields */}
      <section className="space-y-2">
        <div>
          <label className="block text-sm font-semibold text-slate-900 mb-1">
            Qualification fields
          </label>
          <p className="text-xs text-slate-500 mb-3">
            The AI will naturally work these into the conversation to qualify leads.
          </p>
          <QualificationFieldsEditor fields={qualFields} onChange={setQualFields} />
        </div>
      </section>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : saveLabel}
        </button>
      </div>
    </form>
  );
}
