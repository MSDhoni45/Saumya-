import { NextResponse, type NextRequest } from "next/server";

// Must match `auth_access_token_cookie`/`auth_refresh_token_cookie` in
// apps/api/app/core/config.py — the backend names and owns these cookies;
// the frontend only ever reads their presence/refreshes them.
const ACCESS_COOKIE = "wa_access_token";
const REFRESH_COOKIE = "wa_refresh_token";

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

const AUTH_ROUTES = ["/login", "/signup", "/forgot-password", "/reset-password"];
const PROTECTED_PREFIXES = ["/dashboard", "/onboarding", "/inbox", "/leads", "/settings", "/billing", "/analytics", "/agents"];

/**
 * Calls the backend's refresh endpoint with the incoming refresh-token
 * cookie and returns the `Set-Cookie` headers from a successful response —
 * the new session is then re-attached to whatever response middleware
 * ultimately returns (a redirect or a pass-through `next()`).
 *
 * This is the frontend half of "Refresh Tokens": rather than each page
 * independently discovering a stale access token (and bouncing the user to
 * login mid-navigation), middleware refreshes it transparently *before* any
 * route handler or Server Component runs — matching the documented
 * "session refreshed transparently by middleware" contract.
 */
async function refreshSessionCookies(request: NextRequest): Promise<string[] | null> {
  try {
    const response = await fetch(`${BACKEND_API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", cookie: request.headers.get("cookie") ?? "" },
      body: "{}",
    });
    return response.ok ? response.headers.getSetCookie() : null;
  } catch {
    // A transient backend outage shouldn't strand the user on a redirect
    // loop — treat it as "couldn't refresh" and let route-level auth checks
    // (which fail closed) handle it.
    return null;
  }
}

function matchesRoute(path: string, routes: string[]): boolean {
  return routes.some((route) => path === route || path.startsWith(`${route}/`));
}

export async function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;

  let isAuthenticated = request.cookies.has(ACCESS_COOKIE);
  let refreshedCookies: string[] | null = null;

  if (!isAuthenticated && request.cookies.has(REFRESH_COOKIE)) {
    refreshedCookies = await refreshSessionCookies(request);
    isAuthenticated = refreshedCookies !== null;
  }

  const isAuthRoute = matchesRoute(path, AUTH_ROUTES);
  const isProtectedRoute = matchesRoute(path, PROTECTED_PREFIXES);

  let response: NextResponse;
  if (isProtectedRoute && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", path);
    response = NextResponse.redirect(loginUrl);
  } else if (isAuthRoute && isAuthenticated && path !== "/reset-password") {
    // /reset-password is reachable under a *recovery* session even for an
    // already-authenticated browser (the emailed link establishes its own
    // short-lived session) — never bounce it to the dashboard.
    response = NextResponse.redirect(new URL("/dashboard", request.url));
  } else {
    response = NextResponse.next();
  }

  refreshedCookies?.forEach((cookie) => response.headers.append("set-cookie", cookie));
  return response;
}

export const config = {
  // Skip static assets, images, and the backend proxy/rewrite path itself.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|backend).*)"],
};
