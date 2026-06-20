import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { AgentDetailView } from "./agent-detail-view";

export const metadata = { title: "Edit Agent — WhatsAgent AI" };

export default async function AgentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await getSession();
  if (!session || !session.business) redirect("/login");
  if (!session.business) redirect("/onboarding?step=1");

  return <AgentDetailView businessId={session.business.id} agentId={id} />;
}
