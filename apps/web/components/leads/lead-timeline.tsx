"use client";

import { useState } from "react";
import { toast } from "sonner";

import { stageStyle, timelineEventSummary } from "@/lib/leads/format";
import { formatClockTime, formatDayLabel } from "@/lib/inbox/format";
import { useAddNote, useDeleteNote, useLeadTimeline } from "@/lib/leads/queries";
import type { LeadEvent, LeadNote, LeadTimeline } from "@/lib/leads/types";

export function LeadTimeline({
  businessId,
  leadId,
  currentUserId,
}: {
  businessId: string;
  leadId: string;
  currentUserId: string;
}) {
  const query = useLeadTimeline(businessId, leadId);

  if (query.isLoading) return <TimelineSkeleton />;
  if (query.isError)
    return (
      <div className="py-4 text-center text-sm text-slate-500">
        Couldn&apos;t load timeline.{" "}
        <button
          type="button"
          onClick={() => query.refetch()}
          className="underline underline-offset-2 hover:text-slate-700"
        >
          Retry
        </button>
      </div>
    );

  const timeline = query.data!;

  return (
    <div className="space-y-4">
      <TimelineEntries timeline={timeline} businessId={businessId} leadId={leadId} currentUserId={currentUserId} />
      <AddNoteForm businessId={businessId} leadId={leadId} currentUserId={currentUserId} />
    </div>
  );
}

// Merge events + notes into a single sorted list for rendering.
type TimelineEntry =
  | { kind: "event"; item: LeadEvent; ts: string }
  | { kind: "note"; item: LeadNote; ts: string };

function mergeTimeline(timeline: LeadTimeline): TimelineEntry[] {
  const entries: TimelineEntry[] = [
    ...timeline.events.map((e) => ({ kind: "event" as const, item: e, ts: e.created_at })),
    ...timeline.notes.map((n) => ({ kind: "note" as const, item: n, ts: n.created_at })),
  ];
  return entries.sort((a, b) => a.ts.localeCompare(b.ts));
}

function TimelineEntries({
  timeline,
  businessId,
  leadId,
  currentUserId,
}: {
  timeline: LeadTimeline;
  businessId: string;
  leadId: string;
  currentUserId: string;
}) {
  const entries = mergeTimeline(timeline);

  if (entries.length === 0) {
    return <p className="py-4 text-center text-sm text-slate-400">No activity yet.</p>;
  }

  // Group by calendar day
  const days = new Map<string, TimelineEntry[]>();
  for (const entry of entries) {
    const day = formatDayLabel(entry.ts);
    const bucket = days.get(day);
    if (bucket) bucket.push(entry);
    else days.set(day, [entry]);
  }

  return (
    <div className="space-y-4">
      {Array.from(days.entries()).map(([day, dayEntries]) => (
        <div key={day}>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{day}</p>
          <div className="space-y-2">
            {dayEntries.map((entry) =>
              entry.kind === "event" ? (
                <EventRow key={entry.item.id} event={entry.item} />
              ) : (
                <NoteRow
                  key={entry.item.id}
                  note={entry.item}
                  businessId={businessId}
                  leadId={leadId}
                  currentUserId={currentUserId}
                />
              ),
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function EventRow({ event }: { event: LeadEvent }) {
  const summary = timelineEventSummary(event);

  return (
    <div className="flex items-start gap-2.5">
      <EventDot event={event} />
      <div className="min-w-0 flex-1 pt-0.5">
        <p className="text-sm text-slate-700">{summary}</p>
        <p className="mt-0.5 text-xs text-slate-400">{formatClockTime(event.created_at)}</p>
      </div>
    </div>
  );
}

function EventDot({ event }: { event: LeadEvent }) {
  if (event.event_type === "stage_changed") {
    const payload = event.payload as { to: string };
    const s = stageStyle(payload.to);
    return <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${s.dot}`} aria-hidden />;
  }
  return <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-300" aria-hidden />;
}

function NoteRow({
  note,
  businessId,
  leadId,
  currentUserId,
}: {
  note: LeadNote;
  businessId: string;
  leadId: string;
  currentUserId: string;
}) {
  const deleteNote = useDeleteNote(businessId);
  const canDelete = note.author_id === currentUserId;

  const handleDelete = () => {
    deleteNote.mutate(
      { leadId, noteId: note.id, actorId: currentUserId },
      { onError: () => toast.error("Failed to delete note.") },
    );
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <p className="whitespace-pre-wrap text-sm text-slate-800">{note.content}</p>
        {canDelete && (
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteNote.isPending}
            aria-label="Delete note"
            className="shrink-0 rounded p-0.5 text-slate-300 transition hover:bg-red-50 hover:text-red-400 disabled:cursor-not-allowed"
          >
            ✕
          </button>
        )}
      </div>
      <p className="mt-1.5 text-xs text-slate-400">{formatClockTime(note.created_at)}</p>
    </div>
  );
}

function AddNoteForm({
  businessId,
  leadId,
  currentUserId,
}: {
  businessId: string;
  leadId: string;
  currentUserId: string;
}) {
  const [value, setValue] = useState("");
  const addNote = useAddNote(businessId);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    addNote.mutate(
      { leadId, content: trimmed, authorId: currentUserId },
      {
        onSuccess: () => setValue(""),
        onError: () => toast.error("Failed to save note."),
      },
    );
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
        }}
        placeholder="Add a note… (⌘/Ctrl + Enter to save)"
        rows={3}
        className="block w-full resize-none text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
      />
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={submit}
          disabled={!value.trim() || addNote.isPending}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {addNote.isPending ? "Saving…" : "Save note"}
        </button>
      </div>
    </div>
  );
}

function TimelineSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex animate-pulse items-start gap-2.5">
          <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-200" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 w-3/4 rounded bg-slate-200" />
            <div className="h-2.5 w-1/4 rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
}
