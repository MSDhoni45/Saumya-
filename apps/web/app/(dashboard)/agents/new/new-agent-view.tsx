"use client";

import { useRouter } from "next/navigation";

import { AgentForm } from "@/components/agents/agent-form";
import { useCreateAgent } from "@/lib/agents/queries";
import type { CreateAgentRequest } from "@/lib/agents/types";

interface Props {
  businessId: string;
}

export function NewAgentView({ businessId }: Props) {
  const router = useRouter();
  const createMutation = useCreateAgent(businessId);

  async function handleSave(data: CreateAgentRequest) {
    const agent = await createMutation.mutateAsync(data);
    router.push(`/agents/${agent.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => router.push("/agents")}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold text-slate-900">New agent</h1>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <AgentForm
          onSave={handleSave}
          saving={createMutation.isPending}
          saveLabel="Create agent"
        />
      </div>
    </div>
  );
}
