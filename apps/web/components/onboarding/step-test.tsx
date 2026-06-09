"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { PrimaryButton, SecondaryButton, SkipButton, StepActions, StepHeader } from "@/components/onboarding/step-business";
import { useAgents, useTestAgent } from "@/lib/onboarding/queries";
import type { RetrievedChunk, TestMessage } from "@/lib/onboarding/types";

export function StepTest({
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
  const agent = agentsQuery.data?.[0];

  if (agentsQuery.isLoading) {
    return <div className="h-64 animate-pulse rounded-xl bg-slate-100" />;
  }

  if (!agent) {
    return (
      <div className="space-y-8">
        <StepHeader current={5} />
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-5 py-10 text-center">
          <p className="text-sm text-slate-500">No agent configured yet.</p>
          <p className="mt-1 text-xs text-slate-400">Go back to step 4 to create an agent first.</p>
        </div>
        <StepActions>
          <SkipButton onClick={onSkip} />
          <SecondaryButton onClick={onBack}>← Back</SecondaryButton>
        </StepActions>
      </div>
    );
  }

  return <TestChat businessId={businessId} agentId={agent.id} agentName={agent.name} qualFields={agent.qualification_fields} onNext={onNext} onBack={onBack} onSkip={onSkip} />;
}

function TestChat({
  businessId,
  agentId,
  agentName,
  qualFields,
  onNext,
  onBack,
  onSkip,
}: {
  businessId: string;
  agentId: string;
  agentName: string;
  qualFields: { key: string; label: string }[];
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}) {
  const testAgent = useTestAgent(businessId, agentId);
  const [messages, setMessages] = useState<TestMessage[]>([]);
  const [knownFields, setKnownFields] = useState<Record<string, string>>({});
  const [chunks, setChunks] = useState<RetrievedChunk[]>([]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const send = async () => {
    const text = input.trim();
    if (!text) return;

    const newHistory: TestMessage[] = [...messages, { role: "user", content: text }];
    setMessages(newHistory);
    setInput("");

    try {
      const result = await testAgent.mutateAsync({
        message: text,
        history: messages,
        known_lead_fields: knownFields,
      });

      setMessages([...newHistory, { role: "assistant", content: result.reply }]);
      setKnownFields((prev) => ({ ...prev, ...result.extracted_lead_fields }));
      setChunks(result.retrieved_chunks);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch {
      toast.error("Test message failed. Check your API key configuration.");
      setMessages(messages);
    }
  };

  const hasStarted = messages.length > 0;

  return (
    <div className="space-y-6">
      <StepHeader current={5} />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Chat window */}
        <div className="flex flex-col rounded-xl border border-slate-200 bg-white lg:col-span-2">
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
              AI
            </div>
            <span className="text-sm font-medium text-slate-800">{agentName}</span>
            <span className="ml-auto text-xs text-slate-400">Sandbox — no real messages sent</span>
          </div>

          <div className="min-h-[260px] flex-1 overflow-y-auto p-4 space-y-3">
            {!hasStarted && (
              <p className="py-8 text-center text-sm text-slate-400">
                Send a message to start the conversation
              </p>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm ${
                    msg.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-800"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {testAgent.isPending && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-slate-100 px-4 py-3">
                  <div className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="border-t border-slate-100 p-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }}}
              placeholder="Type a test message…"
              disabled={testAgent.isPending}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={send}
              disabled={!input.trim() || testAgent.isPending}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>

        {/* Side panel: extracted fields + retrieved chunks */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Captured fields
            </p>
            {qualFields.length === 0 ? (
              <p className="text-xs text-slate-400">No qualification fields configured.</p>
            ) : (
              <div className="space-y-2">
                {qualFields.map((f) => (
                  <div key={f.key} className="flex items-start gap-2">
                    <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-slate-600">{f.label}</p>
                      <p className="text-xs text-slate-800">
                        {knownFields[f.key] ?? <span className="text-slate-300">—</span>}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {chunks.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Retrieved from KB
              </p>
              <div className="space-y-2">
                {chunks.map((c) => (
                  <div key={c.document_id} className="rounded-md bg-slate-50 p-2">
                    <p className="text-xs font-medium text-slate-700">{c.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-xs text-slate-400">{c.content}</p>
                    <p className="mt-0.5 text-[10px] text-slate-300">
                      {(c.similarity * 100).toFixed(0)}% match
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <StepActions>
        <SkipButton onClick={onSkip} />
        <SecondaryButton onClick={onBack}>← Back</SecondaryButton>
        <PrimaryButton onClick={onNext}>Continue →</PrimaryButton>
      </StepActions>
    </div>
  );
}
