import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { BillingView } from "./billing-view";

export const metadata = { title: "Billing — WhatsAgent AI" };

export default async function BillingPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!session.business) redirect("/onboarding?step=1");

  return <BillingView businessId={session.business.id} />;
}
