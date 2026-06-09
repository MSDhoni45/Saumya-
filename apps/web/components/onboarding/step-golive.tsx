"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { PrimaryButton, SecondaryButton, StepHeader } from "@/components/onboarding/step-business";
import { useAgents, useKnowledgeBases, useUpdateBusiness } from "@/lib/onboarding/queries";
import { useWhatsAppAccounts } from "@/lib/inbox/queries";

export function StepGoLive({
  businessId,
  businessName,
  industry,
  onBack,
}: {
  businessId: string;
  businessName: string;
  industry: string | null;
  onBack: () => void;
}) {
  const router = useRouter();
  const updateBusiness = useUpdateBusiness(businessId);
  const agentsQuery = useAgents(businessId);
  const kbQuery = useKnowledgeBases(businessId);
  const accountsQuery = useWhatsAppAccounts(businessId);

  const agent = agentsQuery.data?.[0];
  const kbs = kbQuery.data ?? [];
  const totalDocs = kbs.reduce((sum, kb) => sum + kb.documents.length, 0);
  const connectedAccounts = (accountsQuery.data ?? []).filter((a) => a.status === "connected");

  const handleGoLive = async () => {
    try {
      await updateBusiness.mutateAsync({ onboarding_completed: true });
      router.push("/dashboard");
      router.refresh();
    } catch {
      toast.error("Something went wrong. Please try again.");
    }
  };

  return (
    <div className="space-y-8">
      <StepHeader current={6} />

      {/* Summary cards */}
      <div className="space-y-3">
        <SummaryRow
          label="Business"
          value={businessName}
          sub={industry ?? "Industry not set"}
          ok={!!industry}
        />
        <SummaryRow
          label="WhatsApp"
          value={
            connectedAccounts.length > 0
              ? `${connectedAccounts.length} account${connectedAccounts.length > 1 ? "s" : ""} connected`
              : "Not connected"
          }
          ok={connectedAccounts.length > 0}
          warn={connectedAccounts.length === 0}
        />
        <SummaryRow
          label="Knowledge base"
          value={totalDocs > 0 ? `${totalDocs} document${totalDocs > 1 ? "s" : ""} added` : "Empty"}
          ok={totalDocs > 0}
          warn={totalDocs === 0}
        />
        <SummaryRow
          label="AI agent"
          value={agent ? agent.name : "Not configured"}
          sub={agent ? `${agent.provider} / ${agent.model}` : undefined}
          ok={!!agent}
          warn={!agent}
        />
      </div>

      {/* Warning callout */}
      {(!agent || connectedAccounts.length === 0) && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <strong>Heads up:</strong> You can still go live and complete the remaining setup later from Settings.
        </div>
      )}

      {/* CTA */}
      <div className="rounded-xl border border-brand-100 bg-brand-50 px-5 py-6 text-center">
        <p className="text-base font-semibold text-brand-900">Ready to go live?</p>
        <p className="mt-1 text-sm text-brand-700">
          Your AI agent will start qualifying leads from WhatsApp conversations.
        </p>
        <div className="mt-4">
          <PrimaryButton onClick={handleGoLive} pending={updateBusiness.isPending}>
            🚀 Go live
          </PrimaryButton>
        </div>
      </div>

      <div className="flex justify-start">
        <SecondaryButton onClick={onBack}>← Back</SecondaryButton>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  sub,
  ok,
  warn,
}: {
  label: string;
  value: string;
  sub?: string;
  ok?: boolean;
  warn?: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
        <p className="mt-0.5 text-sm font-medium text-slate-900">{value}</p>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </div>
      <span
        className={`flex h-7 w-7 items-center justify-center rounded-full text-sm ${
          ok
            ? "bg-emerald-100 text-emerald-600"
            : warn
              ? "bg-amber-100 text-amber-600"
              : "bg-slate-100 text-slate-400"
        }`}
      >
        {ok ? "✓" : "!"}
      </span>
    </div>
  );
}
