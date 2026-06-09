import { redirect } from "next/navigation";

import { WhatsAppSettingsView } from "@/components/settings/whatsapp-settings-view";
import { getSession } from "@/lib/auth/session";

export default async function WhatsAppSettingsPage() {
  const session = await getSession();
  if (!session) redirect("/login");

  const { user, business } = session;

  if (!business) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-slate-500">No business linked to your account.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">WhatsApp Integration</h1>
        <p className="mt-1 text-sm text-slate-500">
          Connect your WhatsApp Business numbers to start receiving and sending messages.
        </p>
      </div>
      <WhatsAppSettingsView businessId={business.id} userRole={user.role} />
    </div>
  );
}
