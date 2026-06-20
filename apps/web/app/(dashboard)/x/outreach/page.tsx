import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { XOutreachView } from "@/components/x/outreach-view";

export default async function XOutreachPage() {
  const session = await getSession();
  if (!session || !session.business) redirect("/login");
  return <XOutreachView businessId={session.business.id} />;
}
