import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { XPostsView } from "@/components/x/posts-view";

export default async function XPostsPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <XPostsView businessId={session.business.id} />;
}
