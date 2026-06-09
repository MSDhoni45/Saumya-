import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { AgentsListView } from "./agents-list-view";

export const metadata = { title: "AI Agents — WhatsAgent AI" };

export default async function AgentsPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!session.business) redirect("/onboarding?step=1");

  return <AgentsListView businessId={session.business.id} />;
}
