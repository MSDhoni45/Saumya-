"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

export function MessageComposer({
  disabled,
  disabledReason,
  isSending,
  onSend,
}: {
  disabled: boolean;
  disabledReason?: string;
  isSending: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isSending) return;
    onSend(trimmed);
    setValue("");
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  };

  if (disabled) {
    return (
      <div className="shrink-0 border-t border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm text-slate-500">
        {disabledReason ?? "You can't reply to this conversation right now."}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="shrink-0 border-t border-slate-200 bg-white p-3">
      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Write a reply… (⌘/Ctrl + Enter to send)"
          rows={1}
          aria-label="Message"
          className="block max-h-40 min-h-[2.5rem] flex-1 resize-none rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <button
          type="submit"
          disabled={!value.trim() || isSending}
          className="flex shrink-0 items-center justify-center rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSending ? "Sending…" : "Send"}
        </button>
      </div>
    </form>
  );
}
