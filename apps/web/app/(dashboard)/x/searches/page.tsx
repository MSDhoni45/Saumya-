import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { XSearchesView } from "@/components/x/searches-view";

export default async function XSearchesPage() {
  const session = await getSession();
  if (!session || !session.business) redirect("/login");
  return <XSearchesView businessId={session.business.id} />;
}
