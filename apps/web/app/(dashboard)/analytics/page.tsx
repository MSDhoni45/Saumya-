import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { AnalyticsView } from "./analytics-view";

export const metadata = { title: "Analytics — WhatsAgent AI" };

export default async function AnalyticsPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!session.business) redirect("/onboarding?step=1");

  return <AnalyticsView businessId={session.business.id} />;
}
