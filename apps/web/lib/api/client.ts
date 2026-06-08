/**
 * Typed fetch wrapper for the FastAPI backend.
 *
 * Requests go through Next's same-origin `/backend/*` rewrite (see
 * next.config.ts) so the httpOnly session cookies FastAPI issues remain
 * first-party — the browser attaches them automatically, and we forward them
 * explicitly on the server (Server Components/Route Handlers don't share the
 * browser's cookie jar).
 *
 * On a 401, we attempt exactly one refresh-and-retry — mirroring the
 * documented "session refreshed transparently" contract — before surfacing
 * the error, so a merely-stale access token never bounces the user to login.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API request failed (${status})`);
  }
}

type FetchOptions = Omit<RequestInit, "body"> & { json?: unknown };

async function rawFetch(path: string, options: FetchOptions = {}): Promise<Response> {
  const isServer = typeof window === "undefined";
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  if (isServer) {
    // Server Components/Route Handlers must forward the incoming cookies —
    // there is no ambient browser cookie jar on this side of the fence.
    // Imported dynamically: `next/headers` is server-only and this module is
    // also imported by client components (the auth forms), which would
    // otherwise fail to bundle.
    const { cookies: nextCookies } = await import("next/headers");
    const cookieStore = await nextCookies();
    headers.set("Cookie", cookieStore.toString());
  }

  const init: RequestInit = {
    ...options,
    headers,
    credentials: "include",
    body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
    cache: "no-store",
  };

  return fetch(`/backend/api/v1${path}`, init);
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function tryRefresh(): Promise<boolean> {
  const response = await rawFetch("/auth/refresh", { method: "POST", json: {} });
  return response.ok;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}, _retried = false): Promise<T> {
  const response = await rawFetch(path, options);

  if (response.status === 401 && !_retried) {
    if (await tryRefresh()) {
      return apiFetch<T>(path, options, true);
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseBody(response));
  }

  return (await parseBody(response)) as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, json?: unknown) => apiFetch<T>(path, { method: "POST", json }),
  patch: <T>(path: string, json?: unknown) => apiFetch<T>(path, { method: "PATCH", json }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
