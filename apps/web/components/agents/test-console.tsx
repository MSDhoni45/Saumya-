"use client";

import { useRef, useState } from "react";

import { useTestAgent } from "@/lib/agents/queries";
import type { RetrievedChunk, TestMessage } from "@/lib/agents/types";
import { ApiError } from "@/lib/api/client";

interface Props {
  businessId: string;
  agentId: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  latency_ms?: number;
  extracted?: Record<string, string>;
  chunks?: RetrievedChunk[];
}

export function TestConsole({ businessId, agentId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [knownFields, setKnownFields] = useState<Record<string, string>>({});
  const [showChunks, setShowChunks] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const testMutation = useTestAgent(businessId, agentId);

  function scrollToBottom() {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  async function send() {
    const text = input.trim();
    if (!text || testMutation.isPending) return;
    setInput("");

    const userMsg: Message = { role: "user", content: text };
    const history: TestMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMsg]);
    scrollToBottom();

    testMutation.mutate(
      { message: text, history, known_lead_fields: knownFields },
      {
        onSuccess: (data) => {
          const extracted = { ...knownFields, ...data.extracted_lead_fields };
          setKnownFields(extracted);
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: data.reply,
              latency_ms: data.latency_ms,
              extracted: Object.keys(data.extracted_lead_fields).length
                ? data.extracted_lead_fields
                : undefined,
              chunks: data.retrieved_chunks.length ? data.retrieved_chunks : undefined,
            },
          ]);
          scrollToBottom();
        },
        onError: (err) => {
          const detail =
            err instanceof ApiError && typeof err.body === "object" && err.body !== null
              ? String((err.body as Record<string, unknown>).detail ?? "Error")
              : "Failed to get a response.";
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `⚠️ ${detail}` },
          ]);
        },
      },
    );
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function reset() {
    setMessages([]);
    setKnownFields({});
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 shrink-0">
        <h3 className="text-sm font-semibold text-slate-900">Live test console</h3>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowChunks(!showChunks)}
            className={`text-xs ${showChunks ? "text-indigo-600" : "text-slate-400"} hover:text-indigo-600`}
          >
            {showChunks ? "Hide" : "Show"} sources
          </button>
          <button
            onClick={reset}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Accumulated lead fields */}
      {Object.keys(knownFields).length > 0 && (
        <div className="border-b border-slate-100 bg-green-50 px-4 py-2 shrink-0">
          <p className="text-xs font-medium text-green-700 mb-1">Captured fields</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(knownFields).map(([k, v]) => (
              <span key={k} className="inline-flex items-center rounded bg-green-100 px-2 py-0.5 text-xs text-green-800">
                <span className="font-medium">{k}:</span>&nbsp;{v}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-xs text-slate-400 text-center pt-8">
            Send a message to test the agent. The AI will respond using your persona and knowledge base.
          </p>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[85%] space-y-1">
              <div
                className={`rounded-xl px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white rounded-br-sm"
                    : "bg-slate-100 text-slate-900 rounded-bl-sm"
                }`}
              >
                {msg.content}
              </div>

              {msg.role === "assistant" && (
                <div className="flex items-center gap-2 px-1">
                  {msg.latency_ms != null && (
                    <span className="text-xs text-slate-400">{msg.latency_ms} ms</span>
                  )}
                  {msg.extracted && (
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(msg.extracted).map(([k, v]) => (
                        <span key={k} className="text-xs bg-amber-50 text-amber-700 rounded px-1">
                          {k}: {v}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {showChunks && msg.chunks && msg.chunks.length > 0 && (
                <div className="mt-1 rounded-lg bg-slate-50 border border-slate-200 p-2 text-xs text-slate-600 space-y-1">
                  <p className="font-medium text-slate-700">Knowledge sources used:</p>
                  {msg.chunks.map((c, j) => (
                    <div key={j} className="flex items-start gap-1">
                      <span className="text-slate-400 shrink-0">{(c.similarity * 100).toFixed(0)}%</span>
                      <span className="font-medium">{c.title}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {testMutation.isPending && (
          <div className="flex justify-start">
            <div className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-400">
              <span className="inline-flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: "0ms" }}>·</span>
                <span className="animate-bounce" style={{ animationDelay: "150ms" }}>·</span>
                <span className="animate-bounce" style={{ animationDelay: "300ms" }}>·</span>
              </span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-100 p-3 shrink-0">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Type a message… (Enter to send)"
            rows={2}
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <button
            onClick={send}
            disabled={!input.trim() || testMutation.isPending}
            className="self-end rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
