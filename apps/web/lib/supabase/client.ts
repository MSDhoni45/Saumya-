import { createBrowserClient } from "@supabase/ssr";

/**
 * Browser-side Supabase client. Used only for the operations that need a
 * direct, real-time relationship with Supabase Auth — establishing the
 * short-lived "recovery" session when a user follows a password-reset link
 * (`onAuthStateChange("PASSWORD_RECOVERY", ...)`). Everything else (signup,
 * login, refresh, session storage) goes through the FastAPI backend, which
 * issues httpOnly cookies — the browser never holds a readable access token.
 */
export function createSupabaseBrowserClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
