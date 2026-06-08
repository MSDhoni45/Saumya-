# 13. Dashboard UI Design

Route: `/dashboard` · Auth: `member` · Data: `GET /dashboard/summary`,
`GET /dashboard/trends`, `GET /dashboard/recent-activity`

## 13.1 Purpose

The dashboard is the first thing a returning user sees — it must answer
"how is my AI workforce performing right now?" at a glance, and surface
anything that needs human attention (handoffs, failed connections, stalled
conversations).

## 13.2 Layout (desktop)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Topbar: org switcher · date-range picker · notifications · profile    │
├──────────────────────────────────────────────────────────────────────┤
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│ │ Conversations│ Leads       │ Appointments│ AI Response │  ← KPI row │
│ │   1,284     │   312       │    47       │   Rate 92%  │           │
│ │  ▲ 12% wow  │  ▲ 8% wow   │  ▲ 3% wow   │  ▼ 1% wow   │           │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘           │
├───────────────────────────────────────┬──────────────────────────────┤
│ Conversations & AI replies over time   │ Recent activity              │
│ (line/area chart, range-selectable)    │ • New lead: Priya Shah       │
│                                        │ • Appointment booked: 3pm    │
│                                        │ • Handoff requested: +91…    │
│                                        │ • Doc "Pricing.pdf" ready    │
├───────────────────────────────────────┴──────────────────────────────┤
│ Lead funnel snapshot (mini funnel) │ Needs attention (handoffs, errors)│
└──────────────────────────────────────────────────────────────────────┘
```

On mobile/tablet the grid stacks vertically in this order: KPI row (2-up
grid) → Needs attention → trend chart → recent activity → funnel snapshot.
"Needs attention" is promoted on small screens because it's the most
actionable section.

## 13.3 Component breakdown

```
DashboardPage (Server Component — fetches initial summary/trends/activity)
└─ DashboardShell (Client)
   ├─ DateRangePicker            — drives `from`/`to` query params for all widgets
   ├─ KpiCardGrid
   │   └─ KpiCard × 4            — value, label, delta vs. previous period, sparkline
   ├─ TrendChartCard
   │   └─ TrendChart             — recharts area/line chart, metric selector
   ├─ RecentActivityFeed
   │   └─ ActivityFeedItem × N   — icon by type, relative timestamp, deep-link
   ├─ LeadFunnelSnapshot
   │   └─ MiniFunnelChart        — stage counts + conversion %, links to /crm
   └─ NeedsAttentionPanel
       └─ AttentionItem × N      — handoff requests, failed sends, expired
                                    connections; each with a one-click resolve action
```

`KpiCard`, `ActivityFeedItem`, and `AttentionItem` are reusable beyond the
dashboard (e.g. `KpiCard` reappears in `/analytics`).

## 13.4 Data flow

- `DashboardPage` (Server Component) fetches the default range (last 30 days)
  server-side and passes it as `initialData` to `DashboardShell`.
- `DashboardShell` owns the `DateRangePicker` state; changing the range
  updates the shared `["org", orgId, "dashboard", { from, to }]` query key,
  refetching all four widgets in parallel via `useQueries`.
- `NeedsAttentionPanel` polls more frequently (`refetchInterval: 30_000`) than
  the rest — it's the section most likely to need a fast human response.
- KPI deltas ("▲ 12% wow") are computed server-side by `/dashboard/summary`
  (it returns the comparison period alongside current values) — the frontend
  never recomputes business metrics.

## 13.5 States

- **Loading**: skeleton cards/charts matching final layout dimensions (no
  layout shift on data arrival).
- **Empty (new organization)**: KPI cards show zeros with a friendly
  "Connect WhatsApp to start seeing activity here" CTA linking to
  `/onboarding`; charts render an illustrated empty state instead of an
  empty axis.
- **Error**: each widget fails independently (one chart erroring doesn't
  blank the page) — inline error card with a retry button per widget.
- **Needs-attention empty state**: a calm "All caught up 🎉" message —
  important that an empty attention panel reads as *good news*, not as a
  missing feature.

## 13.6 Interactions

- Clicking a KPI card deep-links to the relevant filtered view
  (`Conversations` → `/inbox`, `Leads` → `/crm?stage=new`, `Appointments` →
  `/appointments?status=scheduled`, `AI Response Rate` → `/analytics#ai-performance`).
- Activity feed items deep-link to the source record (conversation, lead,
  appointment, document).
- The date-range selection persists per-user (stored in `useUiStore`,
  hydrated from a cookie) so returning to the dashboard preserves context.
