"use client";

import { useRouter } from "next/navigation";

import { useAgents, useDeleteAgent } from "@/lib/agents/queries";
import type { AiAgent } from "@/lib/agents/types";
import { useState } from "react";

const TYPE_LABELS: Record<string, string> = {
  sales: "Sales",
  support: "Support",
  follow_up: "Follow-up",
};

const TYPE_COLORS: Record<string, string> = {
  sales: "bg-blue-50 text-blue-700",
  support: "bg-purple-50 text-purple-700",
  follow_up: "bg-amber-50 text-amber-700",
};

function AgentCard({
  agent,
  businessId,
  onDelete,
}: {
  agent: AiAgent;
  businessId: string;
  onDelete: (id: string) => void;
}) {
  const router = useRouter();
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 flex flex-col gap-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-base font-semibold text-slate-900">{agent.name}</h3>
            <span
              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                TYPE_COLORS[agent.agent_type] ?? "bg-slate-100 text-slate-600"
              }`}
            >
              {TYPE_LABELS[agent.agent_type] ?? agent.agent_type}
            </span>
            <span
              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                agent.is_active ? "bg-green-50 text-green-700" : "bg-slate-100 text-slate-500"
              }`}
            >
              {agent.is_active ? "Active" : "Inactive"}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {agent.provider === "openai" ? "OpenAI" : "Anthropic"} · {agent.model}
          </p>
        </div>
      </div>

      <p className="text-xs text-slate-600 line-clamp-2 flex-1">{agent.persona}</p>

      {agent.qualification_fields.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {(agent.qualification_fields as Array<{ key: string; label: string }>).map((f) => (
            <span
              key={f.key}
              className="inline-flex rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700"
            >
              {f.key}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
        <button
          onClick={() => router.push(`/agents/${agent.id}`)}
          className="flex-1 rounded-lg border border-slate-200 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          Edit & Test
        </button>
        {confirmDelete ? (
          <>
            <button
              onClick={() => {
                onDelete(agent.id);
                setConfirmDelete(false);
              }}
              className="flex-1 rounded-lg bg-red-600 py-1.5 text-xs font-medium text-white hover:bg-red-700"
            >
              Confirm delete
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="text-xs text-slate-400 hover:text-slate-600 px-2"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="text-xs text-slate-400 hover:text-red-500 px-2"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

interface Props {
  businessId: string;
}

export function AgentsListView({ businessId }: Props) {
  const router = useRouter();
  const { data: agents, isLoading } = useAgents(businessId);
  const deleteMutation = useDeleteAgent(businessId);

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">AI Agents</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Configure the AI agents that handle your WhatsApp conversations.
          </p>
        </div>
        <button
          onClick={() => router.push("/agents/new")}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          New agent
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      ) : agents && agents.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              businessId={businessId}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50">
            <span className="text-2xl">🤖</span>
          </div>
          <h3 className="text-sm font-semibold text-slate-900">No agents yet</h3>
          <p className="mt-1 text-sm text-slate-500">
            Create your first AI agent to start automating WhatsApp conversations.
          </p>
          <button
            onClick={() => router.push("/agents/new")}
            className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Create your first agent
          </button>
        </div>
      )}
    </div>
  );
}
