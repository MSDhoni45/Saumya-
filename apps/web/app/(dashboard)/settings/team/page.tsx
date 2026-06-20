import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { TeamView } from "./team-view";

export const metadata = { title: "Team — WhatsAgent AI" };

export default async function TeamPage() {
  const session = await getSession();
  if (!session || !session.business) redirect("/login");
  if (!session.business) redirect("/onboarding?step=1");

  return (
    <TeamView
      businessId={session.business.id}
      currentUserId={session.user.id}
      currentRole={session.user.role}
    />
  );
}
