import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { XConnectView } from "@/components/x/connect-view";

export default async function XConnectPage({
  searchParams,
}: {
  searchParams: Promise<{ connected?: string; username?: string; error?: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/login");

  const params = await searchParams;

  return (
    <XConnectView
      businessId={session.business.id}
      connected={params.connected === "true"}
      username={params.username}
      error={params.error}
    />
  );
}
