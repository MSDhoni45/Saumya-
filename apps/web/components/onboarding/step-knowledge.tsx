"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { PrimaryButton, SecondaryButton, SkipButton, StepActions, StepHeader } from "@/components/onboarding/step-business";
import { useAddDocument, useCreateKb, useDeleteDocument, useKnowledgeBases } from "@/lib/onboarding/queries";
import type { KnowledgeBase } from "@/lib/onboarding/types";

type Tab = "text" | "url";

interface DocFormValues {
  title: string;
  content: string;
  url: string;
}

export function StepKnowledge({
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
  const kbQuery = useKnowledgeBases(businessId);
  const createKb = useCreateKb(businessId);
  const kbs = kbQuery.data ?? [];
  const activeKb: KnowledgeBase | undefined = kbs[0];

  const handleEnsureKb = async () => {
    if (activeKb) return activeKb;
    return createKb.mutateAsync({ name: "Main knowledge base" });
  };

  return (
    <div className="space-y-8">
      <StepHeader current={3} />

      <div className="space-y-3">
        <p className="text-sm text-slate-600">
          Add content your AI agent can reference when answering customer questions — FAQs, product
          descriptions, pricing, policies.
        </p>

        {kbQuery.isLoading ? (
          <div className="h-32 w-full animate-pulse rounded-xl bg-slate-100" />
        ) : (
          <KbPanel businessId={businessId} kb={activeKb} onEnsureKb={handleEnsureKb} />
        )}
      </div>

      <StepActions>
        <SkipButton onClick={onSkip} />
        <SecondaryButton onClick={onBack}>← Back</SecondaryButton>
        <PrimaryButton onClick={onNext}>Continue →</PrimaryButton>
      </StepActions>
    </div>
  );
}

function KbPanel({
  businessId,
  kb,
  onEnsureKb,
}: {
  businessId: string;
  kb: KnowledgeBase | undefined;
  onEnsureKb: () => Promise<KnowledgeBase>;
}) {
  const [tab, setTab] = useState<Tab>("text");
  const [showForm, setShowForm] = useState(false);
  const addDoc = useAddDocument(businessId, kb?.id ?? "");
  const deleteDoc = useDeleteDocument(businessId, kb?.id ?? "");

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<DocFormValues>({
    defaultValues: { title: "", content: "", url: "" },
  });

  const onSubmit = async (values: DocFormValues) => {
    const resolvedKb = await onEnsureKb();
    try {
      if (tab === "text") {
        await addDoc.mutateAsync({
          title: values.title.trim(),
          content: values.content.trim(),
          source_type: "text",
        });
      } else {
        await addDoc.mutateAsync({
          title: values.title.trim(),
          content: `Source URL: ${values.url.trim()}`,
          source_type: "url",
          source_url: values.url.trim(),
        });
      }
      reset();
      setShowForm(false);
      toast.success("Document added.");
    } catch {
      toast.error("Failed to add document.");
    }
    void resolvedKb;
  };

  const docs = kb?.documents ?? [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      {/* Doc list */}
      {docs.length > 0 && (
        <div className="divide-y divide-slate-100">
          {docs.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800">{doc.title}</p>
                <p className="mt-0.5 text-xs text-slate-400 capitalize">
                  {doc.source_type} ·{" "}
                  <span
                    className={
                      doc.status === "ready"
                        ? "text-emerald-600"
                        : doc.status === "error"
                          ? "text-red-500"
                          : "text-amber-500"
                    }
                  >
                    {doc.status === "ready" ? "Indexed" : doc.status === "error" ? "Error" : "Processing…"}
                  </span>
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  deleteDoc.mutate(doc.id, {
                    onError: () => toast.error("Failed to delete document."),
                  })
                }
                className="ml-3 shrink-0 p-1 text-slate-300 hover:text-red-400"
                aria-label="Delete document"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add form */}
      {showForm ? (
        <form onSubmit={handleSubmit(onSubmit)} className="border-t border-slate-100 p-4 space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 rounded-md border border-slate-200 p-0.5 w-fit">
            {(["text", "url"] as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={`rounded px-3 py-1 text-xs font-medium transition ${
                  tab === t ? "bg-slate-800 text-white" : "text-slate-500 hover:bg-slate-50"
                }`}
              >
                {t === "text" ? "Paste text" : "Add URL"}
              </button>
            ))}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Title</label>
            <input
              {...register("title", { required: "Title is required" })}
              placeholder="e.g. Pricing FAQ"
              className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            {errors.title && <p className="mt-0.5 text-xs text-red-500">{errors.title.message}</p>}
          </div>

          {tab === "text" ? (
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Content</label>
              <textarea
                {...register("content", { required: "Content is required" })}
                rows={5}
                placeholder="Paste the content your AI should know…"
                className="block w-full resize-none rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              {errors.content && <p className="mt-0.5 text-xs text-red-500">{errors.content.message}</p>}
            </div>
          ) : (
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">URL</label>
              <input
                {...register("url", { required: "URL is required" })}
                type="url"
                placeholder="https://your-site.com/faq"
                className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              {errors.url && <p className="mt-0.5 text-xs text-red-500">{errors.url.message}</p>}
              <p className="mt-1 text-xs text-slate-400">We&apos;ll import and index this page&apos;s content.</p>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <SecondaryButton onClick={() => { setShowForm(false); reset(); }}>Cancel</SecondaryButton>
            <PrimaryButton type="submit" pending={isSubmitting || addDoc.isPending}>
              Add document
            </PrimaryButton>
          </div>
        </form>
      ) : (
        <div className={docs.length > 0 ? "border-t border-slate-100" : ""}>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="flex w-full items-center justify-center gap-2 px-4 py-5 text-sm font-medium text-slate-500 transition hover:text-brand-600"
          >
            + Add a document
          </button>
        </div>
      )}
    </div>
  );
}
