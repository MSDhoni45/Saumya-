"use client";

import { useRouter } from "next/navigation";

import { AgentForm } from "@/components/agents/agent-form";
import { TestConsole } from "@/components/agents/test-console";
import { useAgent, useUpdateAgent } from "@/lib/agents/queries";
import type { CreateAgentRequest } from "@/lib/agents/types";

interface Props {
  businessId: string;
  agentId: string;
}

export function AgentDetailView({ businessId, agentId }: Props) {
  const router = useRouter();
  const { data: agent, isLoading, error } = useAgent(businessId, agentId);
  const updateMutation = useUpdateAgent(businessId, agentId);

  async function handleSave(data: CreateAgentRequest) {
    await updateMutation.mutateAsync(data);
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-100 mb-6" />
        <div className="h-96 animate-pulse rounded-xl bg-slate-100" />
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-sm text-red-600">Agent not found.</p>
        <button
          onClick={() => router.push("/agents")}
          className="mt-2 text-sm text-indigo-600 hover:underline"
        >
          Back to agents
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => router.push("/agents")}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold text-slate-900">{agent.name}</h1>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            agent.is_active ? "bg-green-50 text-green-700" : "bg-slate-100 text-slate-500"
          }`}
        >
          {agent.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_400px]">
        {/* Left: Edit form */}
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Configuration</h2>
          <AgentForm
            initial={agent}
            onSave={handleSave}
            saving={updateMutation.isPending}
            saveLabel={updateMutation.isSuccess ? "Saved ✓" : "Save changes"}
          />
        </div>

        {/* Right: Test console */}
        <div className="rounded-xl border border-slate-200 bg-white" style={{ height: "calc(100vh - 200px)", minHeight: 480 }}>
          <TestConsole businessId={businessId} agentId={agentId} />
        </div>
      </div>
    </div>
  );
}
