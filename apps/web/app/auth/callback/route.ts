import { createClient } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";

/**
 * Lands here from the "confirm your email" link Supabase sends after signup
 * (when email confirmation is enabled on the project — configure the email
 * template's action link as `{{ .SiteURL }}/auth/callback?token_hash={{
 * .TokenHash }}&type=signup`).
 *
 * We verify the token server-side — which is what actually marks the email
 * confirmed — and deliberately *don't* try to adopt the resulting Supabase
 * session into our cookies: signup itself happened through the backend (see
 * app/api/v1/auth.py::signup), which has no record of a browser-held PKCE
 * code verifier to complete that exchange. Instead we redirect to `/login`,
 * where the user signs in normally and the backend mints its own session —
 * one consistent path for every credential/session operation.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type");

  if (tokenHash && type === "signup") {
    const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!);
    const { error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type: "signup" });
    if (!error) {
      return NextResponse.redirect(`${origin}/login?confirmed=1`);
    }
  }

  return NextResponse.redirect(`${origin}/login?confirmed=0`);
}
