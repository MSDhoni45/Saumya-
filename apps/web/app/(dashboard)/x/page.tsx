import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { XDashboardView } from "@/components/x/dashboard-view";

export default async function XDashboardPage() {
  const session = await getSession();
  if (!session || !session.business) redirect("/login");
  return <XDashboardView businessId={session.business.id} />;
}
