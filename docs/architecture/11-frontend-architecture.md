# 11. Next.js Frontend Architecture

This expands `01-system-architecture.md` and `04-folder-structure.md` into a
concrete frontend design: rendering strategy, data flow, state management,
styling conventions, and how the app stays in sync with the FastAPI/Supabase
backend.

## 11.1 Routing & route groups (App Router)

```
app/
├── (marketing)/        # public, statically-rendered where possible
├── (auth)/             # signup/login/reset — redirect away if already authenticated
├── onboarding/         # post-signup guided setup wizard (authenticated, org has no WhatsApp connection yet)
└── (dashboard)/        # authenticated product surface — protected by middleware + layout guard
```

Route groups isolate layouts and middleware behavior without affecting URLs.
`middleware.ts` refreshes the Supabase session cookie on every request and
redirects: unauthenticated users away from `(dashboard)`/`onboarding`,
authenticated users away from `(auth)`, and users without a connected
WhatsApp number from `(dashboard)` toward `/onboarding` until they complete
(or explicitly skip) it.

## 11.2 Rendering strategy — Server vs. Client Components

| Use Server Components for | Use Client Components for |
|---|---|
| Marketing pages (SEO, fast first paint) | Anything with interaction: forms, the inbox, the CRM kanban board, charts, the agent persona editor |
| Initial authenticated page shells (fetch the first page of data server-side, stream it in) | Anything subscribed to Realtime updates or polling |
| Layouts that read the session/org cookie | Anything using browser-only APIs (drag-and-drop, file upload progress, websockets) |

Pattern: a Server Component fetches the **first page** of data (e.g. the
first 25 conversations) and passes it as `initialData` to a Client Component
that owns the interactive list, pagination, filters, and live updates via
TanStack Query (`useQuery({ initialData })`). This gives fast first paint
without sacrificing the rich client interactivity these screens need.

## 11.3 Data fetching & server-state management — TanStack Query

All reads/writes against FastAPI go through a typed client
(`lib/api/client.ts`, built on `fetch`/`ky`) wrapped in **TanStack Query**
hooks (`lib/api/hooks/*`), one module per domain mirroring the backend
routers (`useConversations`, `useLeads`, `useKnowledgeBaseDocuments`, …).

Conventions:
- **Query keys** are structured arrays scoped by org:
  `["org", orgId, "leads", { stage, search, page }]` — switching organizations
  invalidates everything under `["org", orgId]` automatically.
- **Mutations** use `onMutate`/optimistic updates for snappy interactions
  (e.g. dragging a lead card between kanban columns updates instantly, rolls
  back on error) and invalidate the relevant query keys on settle.
- **Pagination**: `useInfiniteQuery` for the inbox message thread (cursor-based,
  matches the backend's `before`/`next_cursor` contract); `useQuery` with
  page params for list views (leads, appointments, documents).
- A shared `apiFetch` wrapper attaches `Authorization` (from the Supabase
  session) and `X-Org-Id` (from the org-switcher store) headers, centralizes
  error parsing into the `{ error: { code, message, details } }` envelope, and
  triggers a session refresh + retry on `401`.

## 11.4 Client-side state — Zustand (sparingly)

Server state lives in TanStack Query. A small set of **ephemeral UI state**
lives in lightweight Zustand stores (`stores/`):
- `useOrgStore` — active `organization_id` + role (persisted to a cookie so
  middleware and server components can read it too).
- `useInboxUiStore` — selected conversation, filter/search state, composer
  draft text (so it survives navigating the contact panel).
- `useUiStore` — sidebar collapsed state, command-palette open state, theme.

No global Redux-style store — most state is either server state (Query) or
local component state (`useState`/`useReducer`).

## 11.5 Real-time updates

The inbox and dashboard need live updates when new WhatsApp messages arrive.
Two layers:
1. **Supabase Realtime** (Postgres logical replication over websockets):
   the inbox subscribes to `INSERT`/`UPDATE` on `messages`/`conversations`
   filtered by `organization_id` (RLS-aware — the client only receives rows it
   can already SELECT). On event, TanStack Query cache is patched directly
   (`queryClient.setQueryData`) for instant UI updates without a refetch.
2. **Polling fallback** (`refetchInterval`) for dashboards/analytics where
   sub-second latency doesn't matter and Realtime would be overkill.

## 11.6 Forms & validation

`react-hook-form` + `zod` schemas that **mirror the backend Pydantic request
models** (kept alongside the generated API types in `types/api/`, hand-written
where the backend doesn't expose a schema 1:1, e.g. multi-step onboarding
forms that compose several backend calls). `zodResolver` wires validation
into `react-hook-form`; shadcn's `Form` primitives render fields, errors, and
descriptions consistently across the app.

## 11.7 Styling & UI conventions

- **Tailwind** for layout/spacing/typography utilities; a small `theme`
  extension in `tailwind.config.ts` defines the brand palette, radii, and
  shadows as design tokens (also exposed as CSS variables for shadcn).
- **shadcn/ui** primitives (`components/ui/`) are the base vocabulary —
  buttons, inputs, dialogs, dropdowns, tables, tabs, toasts, sheets/drawers,
  command palette. Feature components compose these rather than reinventing them.
- **Icons**: `lucide-react` (shadcn's default), consistent sizing via a
  shared `Icon` wrapper.
- **Dark mode**: supported via Tailwind's `class` strategy + a theme toggle
  (`next-themes`), since support agents may run the inbox for long stretches.
- **Toasts** (`sonner`/shadcn `Toast`) for mutation feedback (success/error),
  not for validation errors (those render inline via `react-hook-form`).

## 11.8 Type-safety bridge to the backend

`openapi-typescript` generates `types/api/schema.d.ts` from FastAPI's
`/openapi.json` as a build/dev-time step (`pnpm generate:api-types`). The
typed `apiFetch<T>` client and all Query/mutation hooks consume these types —
when the backend changes a response shape, the frontend fails to compile
until it's addressed. This removes an entire class of drift bugs between the
two codebases.

## 11.9 Error & loading states

- **Route-level**: `loading.tsx` (skeletons matching the eventual layout) and
  `error.tsx` (retry affordance + Sentry capture) per route segment.
- **Component-level**: TanStack Query's `isPending`/`isError` states render
  skeleton placeholders / inline error cards with retry buttons — never a
  blank screen.
- **Empty states**: every list/board has a designed empty state (e.g. "No
  leads yet — they'll appear here as your AI agent qualifies conversations,"
  with a CTA to view the inbox or invite teammates).
- **Global**: a top-level `error.tsx`/`global-error.tsx` boundary plus Sentry
  for unhandled exceptions; toast notifications for transient mutation failures.

## 11.10 Performance

- Server Components + streaming (`<Suspense>`) for fast first paint on
  data-heavy pages (dashboard, analytics).
- Route-level code splitting is automatic with the App Router; heavy
  client-only libraries (charting, drag-and-drop, rich text) are
  `next/dynamic`-imported where they'd otherwise bloat shared bundles.
- `next/image` for all avatars/media with the Supabase Storage domain
  allow-listed.
- TanStack Query's cache + `staleTime` tuning avoids redundant refetches when
  navigating between already-visited views (e.g. inbox ⇄ CRM).

## 11.11 Accessibility & responsiveness

- shadcn/Radix primitives provide keyboard navigation and ARIA semantics out
  of the box; feature components preserve focus management (especially in
  the inbox composer and CRM drawers).
- Mobile breakpoints: the three-pane inbox collapses to a single-pane
  navigable stack; the CRM kanban becomes a filterable list (see
  `15-whatsapp-inbox-ui-design.md` and `14-crm-ui-design.md` for specifics).
