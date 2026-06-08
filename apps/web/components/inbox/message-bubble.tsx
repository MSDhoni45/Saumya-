import { formatClockTime } from "@/lib/inbox/format";
import type { Message } from "@/lib/inbox/types";

export function MessageBubble({ message }: { message: Message }) {
  if (message.sender_type === "system") {
    return (
      <div className="flex justify-center py-1">
        <span className="rounded-full bg-slate-100 px-3 py-1 text-center text-xs text-slate-500">{message.content}</span>
      </div>
    );
  }

  const isOutgoing = message.sender_type === "ai" || message.sender_type === "agent";

  return (
    <div className={`flex ${isOutgoing ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[75%] space-y-1">
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed shadow-sm ${
            message.sender_type === "ai"
              ? "rounded-br-sm bg-brand-50 text-brand-900 ring-1 ring-inset ring-brand-100"
              : message.sender_type === "agent"
                ? "rounded-br-sm bg-brand-600 text-white"
                : "rounded-bl-sm bg-white text-slate-800 ring-1 ring-inset ring-slate-200"
          }`}
        >
          {message.sender_type === "ai" && (
            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-brand-500">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" aria-hidden />
              AI reply
            </p>
          )}
          <MessageContent message={message} isOutgoing={isOutgoing} />
        </div>
        <p className={`px-1 text-[11px] text-slate-400 ${isOutgoing ? "text-right" : "text-left"}`}>
          {formatClockTime(message.created_at)}
          {message.status === "queued" && <span className="ml-1.5 text-slate-400">Sending…</span>}
          {message.status === "failed" && <span className="ml-1.5 font-medium text-red-500">Failed to send</span>}
        </p>
      </div>
    </div>
  );
}

function MessageContent({ message, isOutgoing }: { message: Message; isOutgoing: boolean }) {
  if (message.message_type === "text" || !message.media_url) {
    return <p className="whitespace-pre-wrap break-words">{message.content || "—"}</p>;
  }

  const linkClasses = isOutgoing ? "text-white underline" : "text-brand-700 underline";

  return (
    <div className="space-y-1.5">
      {message.message_type === "image" ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote, business-controlled WhatsApp media URL
        <img
          src={message.media_url}
          alt={message.content ?? "Image attachment"}
          className="max-h-64 w-full rounded-lg object-cover"
        />
      ) : (
        <a href={message.media_url} target="_blank" rel="noreferrer" className={`block text-sm font-medium underline-offset-2 ${linkClasses}`}>
          {message.content || "Open attachment"}
        </a>
      )}
      {message.content && message.message_type === "image" && <p>{message.content}</p>}
    </div>
  );
}
