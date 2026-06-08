"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";

export function SignOutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  const handleSignOut = async () => {
    setPending(true);
    try {
      await api.post("/auth/logout");
    } finally {
      router.push("/login");
      router.refresh();
    }
  };

  return (
    <button
      type="button"
      onClick={handleSignOut}
      disabled={pending}
      className="font-medium text-slate-500 hover:text-slate-700 disabled:opacity-60"
    >
      {pending ? "Signing out…" : "Sign out"}
    </button>
  );
}
