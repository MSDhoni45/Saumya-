"use client";

import { useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { toast } from "sonner";

import { PrimaryButton, SecondaryButton, SkipButton, StepActions, StepHeader } from "@/components/onboarding/step-business";
import { useAgents, useCreateAgent, useUpdateAgent } from "@/lib/onboarding/queries";
import type { QualificationField } from "@/lib/onboarding/types";

const MODELS = {
  openai: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
  anthropic: [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
  ],
} as const;

const DEFAULT_PERSONA =
  "You are a friendly, knowledgeable sales assistant. Be concise and helpful. Never invent facts about the business.";

const DEFAULT_FIELDS: QualificationField[] = [
  { key: "budget", label: "Budget range", required: false },
  { key: "service_interested", label: "Service or product you're interested in", required: false },
];

interface FormValues {
  name: string;
  agent_type: "sales" | "support" | "follow_up";
  persona: string;
  provider: "openai" | "anthropic";
  model: string;
  temperature: number;
  qualification_fields: QualificationField[];
}

export function StepAgent({
  businessId,
  onNext,
  onBack,
  onSkip,
}: {
  businessId: string;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}) {
  const agentsQuery = useAgents(businessId);
  const createAgent = useCreateAgent(businessId);
  const existingAgent = agentsQuery.data?.[0];
  const updateAgent = useUpdateAgent(businessId, existingAgent?.id ?? "");

  const { register, handleSubmit, watch, reset, control, formState: { errors, isSubmitting } } = useForm<FormValues>({
    defaultValues: {
      name: "Sales Assistant",
      agent_type: "sales",
      persona: DEFAULT_PERSONA,
      provider: "openai",
      model: "gpt-4o-mini",
      temperature: 0.4,
      qualification_fields: DEFAULT_FIELDS,
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "qualification_fields" });
  const selectedProvider = watch("provider");

  useEffect(() => {
    if (existingAgent) {
      reset({
        name: existingAgent.name,
        agent_type: existingAgent.agent_type,
        persona: existingAgent.persona,
        provider: existingAgent.provider,
        model: existingAgent.model,
        temperature: Number(existingAgent.temperature),
        qualification_fields:
          existingAgent.qualification_fields.length > 0
            ? existingAgent.qualification_fields
            : DEFAULT_FIELDS,
      });
    }
  }, [existingAgent, reset]);

  const onSubmit = async (values: FormValues) => {
    try {
      if (existingAgent) {
        await updateAgent.mutateAsync(values);
      } else {
        await createAgent.mutateAsync({ ...values, is_active: true });
      }
      onNext();
    } catch {
      toast.error("Failed to save agent configuration.");
    }
  };

  if (agentsQuery.isLoading) {
    return <div className="h-64 w-full animate-pulse rounded-xl bg-slate-100" />;
  }

  const availableModels = MODELS[selectedProvider] ?? MODELS.openai;

  return (
    <div className="space-y-8">
      <StepHeader current={4} />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Basic info */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Agent name</label>
            <input
              {...register("name", { required: "Required" })}
              className={inputClass}
              placeholder="Sales Assistant"
            />
            {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Type</label>
            <select {...register("agent_type")} className={inputClass}>
              <option value="sales">Sales</option>
              <option value="support">Support</option>
              <option value="follow_up">Follow-up</option>
            </select>
          </div>
        </div>

        {/* Persona */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">
            Persona / system prompt
          </label>
          <textarea
            {...register("persona")}
            rows={4}
            className={`${inputClass} resize-none`}
            placeholder={DEFAULT_PERSONA}
          />
          <p className="mt-1 text-xs text-slate-400">
            Describes how the agent should behave and what it knows about your business.
          </p>
        </div>

        {/* Model settings */}
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Provider</label>
            <select {...register("provider")} className={inputClass}>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Model</label>
            <select {...register("model")} className={inputClass}>
              {availableModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Temperature — {watch("temperature")}
            </label>
            <input
              {...register("temperature", { valueAsNumber: true })}
              type="range"
              min={0}
              max={1}
              step={0.1}
              className="w-full accent-brand-600"
            />
            <div className="mt-0.5 flex justify-between text-[10px] text-slate-400">
              <span>Focused</span><span>Creative</span>
            </div>
          </div>
        </div>

        {/* Qualification fields */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-slate-700">Qualification fields</label>
              <p className="text-xs text-slate-400">
                Fields the agent will naturally try to capture during conversation.
              </p>
            </div>
            <button
              type="button"
              onClick={() => append({ key: "", label: "", required: false })}
              className="text-xs font-medium text-brand-600 hover:text-brand-700"
            >
              + Add field
            </button>
          </div>

          <div className="space-y-2">
            {fields.map((field, idx) => (
              <div key={field.id} className="flex items-center gap-2">
                <input
                  {...register(`qualification_fields.${idx}.key`, { required: true })}
                  placeholder="key"
                  className="w-28 rounded-md border border-slate-300 px-2 py-1.5 text-xs font-mono focus:border-brand-500 focus:outline-none"
                />
                <input
                  {...register(`qualification_fields.${idx}.label`, { required: true })}
                  placeholder="Human-readable label for AI"
                  className="flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-xs focus:border-brand-500 focus:outline-none"
                />
                <label className="flex items-center gap-1 text-xs text-slate-500">
                  <input
                    {...register(`qualification_fields.${idx}.required`)}
                    type="checkbox"
                    className="accent-brand-600"
                  />
                  Required
                </label>
                <button
                  type="button"
                  onClick={() => remove(idx)}
                  className="shrink-0 p-0.5 text-slate-300 hover:text-red-400"
                  aria-label="Remove field"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>

        <StepActions>
          <SkipButton onClick={onSkip} />
          <SecondaryButton onClick={onBack}>← Back</SecondaryButton>
          <PrimaryButton type="submit" pending={isSubmitting || createAgent.isPending || updateAgent.isPending}>
            {existingAgent ? "Save & continue →" : "Create agent →"}
          </PrimaryButton>
        </StepActions>
      </form>
    </div>
  );
}

const inputClass =
  "block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";
