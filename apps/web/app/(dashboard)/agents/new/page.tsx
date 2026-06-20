import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { NewAgentView } from "./new-agent-view";

export const metadata = { title: "New Agent — WhatsAgent AI" };

export default async function NewAgentPage() {
  const session = await getSession();
  if (!session || !session.business) redirect("/login");
  if (!session.business) redirect("/onboarding?step=1");

  return <NewAgentView businessId={session.business.id} />;
}
