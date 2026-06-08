import { cache } from "react";

import { ApiError, apiFetch } from "@/lib/api/client";
import type { MeResponse } from "@/lib/auth/rbac";

/**
 * Resolves the current session for Server Components/layouts by calling the
 * backend's `/auth/me` with the forwarded session cookies. `cache()` so a
 * single request only resolves the session once even when several layouts/
 * pages in the same render tree need it (middleware already guarantees the
 * access-token cookie is fresh — see middleware.ts).
 *
 * Returns `null` for an unauthenticated visitor rather than throwing — call
 * sites decide whether that's an error (protected routes redirect via
 * middleware before this ever runs) or expected (the (auth) layout uses this
 * to bounce already-logged-in users away from /login).
 */
export const getSession = cache(async (): Promise<MeResponse | null> => {
  try {
    return await apiFetch<MeResponse>("/auth/me", { method: "GET" });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
});
