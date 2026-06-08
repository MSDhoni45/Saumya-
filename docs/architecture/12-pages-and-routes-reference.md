# 12. Pages & Routes Reference

Every route in `apps/web`, grouped by route group, with purpose, auth
requirement, primary data dependencies, and key components. "Auth" follows
the same levels as the API reference: `none` (public), `user` (signed in,
no org requirement), `member`/`admin` (signed in + active membership/role in
the active org).

---

## 12.1 `(marketing)` — public

| Route | Purpose | Auth | Notes |
|---|---|---|---|
| `/` | Landing page: value prop, feature highlights, CTA to signup | none | Server Component, statically generated |
| `/pricing` | Plan comparison | none | Static |
| `/about`, `/contact` | Company/contact info | none | Static |
| `/legal/privacy`, `/legal/terms` | Legal pages | none | Static |

## 12.2 `(auth)` — authentication

| Route | Purpose | Auth | Notes |
|---|---|---|---|
| `/login` | Email/password sign-in | `none` (redirects to `/dashboard` if already signed in) | Calls `supabase.auth.signInWithPassword` |
| `/signup` | Account + business creation | `none` | Calls `supabase.auth.signUp`, then `POST /auth/bootstrap` on first load of the dashboard |
| `/forgot-password` | Request a reset email | `none` | Calls `supabase.auth.resetPasswordForEmail` |
| `/reset-password` | Set a new password from the emailed link | `none` (requires a valid recovery session) | Calls `supabase.auth.updateUser` |
| `/accept-invite` | Accept a team invite (`?token=`) | `user` | Calls `POST /auth/invites/accept`; prompts sign-up/sign-in first if needed |
| `/verify-email` | "Check your inbox" / confirmation landing | `none` | Shown when email confirmation is enabled |

## 12.3 `/onboarding` — guided setup wizard

| Route | Purpose | Auth | Notes |
|---|---|---|---|
| `/onboarding` | Multi-step wizard: connect WhatsApp → upload knowledge → configure agent → (optional) connect calendar → go live | `member` (owner/admin to complete connection steps; agents see a "waiting on your admin" state) | See `16-onboarding-flow.md`. Steps are deep-linkable (`/onboarding?step=whatsapp`) and resumable |

## 12.4 `(dashboard)` — authenticated product surface

All routes below share the dashboard layout (sidebar + topbar + org switcher,
`app/(dashboard)/layout.tsx`) and require `member` unless noted.

### Overview
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/dashboard` | KPI overview + trends + recent activity | `/dashboard/summary`, `/dashboard/trends`, `/dashboard/recent-activity` | `KpiCardGrid`, `TrendChart`, `RecentActivityFeed` (see §13) |

### Inbox
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/inbox` | Conversation list + empty thread state | `GET /conversations` | `ConversationList`, `EmptyThreadPlaceholder` |
| `/inbox/[conversationId]` | Three-pane inbox: list, thread, contact/lead context | `GET /conversations/{id}`, `GET /conversations/{id}/messages` (+ Realtime) | `ConversationList`, `MessageThread`, `Composer`, `ContactContextPanel` (see §15) |

### Knowledge base
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/knowledge-base` | Document/URL list with ingestion status, upload UI | `GET /knowledge-base/documents` | `DocumentTable`, `UploadDropzone`, `AddUrlDialog`, `StatusBadge` |
| `/knowledge-base/[documentId]` | Document detail: chunks, status, failure reason, reprocess | `GET /knowledge-base/documents/{id}` | `DocumentDetailCard`, `ChunkPreviewList` |

### AI agents
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/agents` | List of configured agents (sales, follow-up, support) | `GET /agents` | `AgentCard` grid |
| `/agents/[agentId]` | Persona/prompt editor, model/provider selection, qualification fields, sandbox tester | `GET /agents/{id}`, `POST /agents/{id}/test` | `PersonaEditor`, `ModelProviderSelect`, `QualificationFieldsEditor`, `AgentTestSandbox` |

### CRM
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/crm` | Kanban pipeline across lead stages (list view on mobile) | `GET /leads` | `LeadKanbanBoard`, `LeadListView`, `LeadFilterBar` |
| `/crm/[leadId]` | Lead detail: qualification fields, activity timeline, notes, linked conversation/appointments | `GET /leads/{id}`, `GET /leads/{id}/activities` | `LeadDetailHeader`, `ActivityTimeline`, `NoteComposer` (see §14) |

### Appointments
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/appointments` | Calendar/list view of bookings, manual booking | `GET /appointments`, `GET /calendar/availability` | `AppointmentCalendarView`, `AppointmentListView`, `BookAppointmentDialog` |
| `/appointments/[appointmentId]` | Detail/reschedule/cancel | `GET /appointments/{id}` | `AppointmentDetailCard`, `RescheduleDialog` |

### Follow-ups
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/follow-ups` | Sequence list + active enrollment counts | `GET /follow-ups/sequences` | `SequenceCard` grid |
| `/follow-ups/[sequenceId]` | Sequence builder (steps, delays, templates), enrollment list | `GET /follow-ups/sequences/{id}`, `GET /follow-ups/enrollments?sequence_id=` | `SequenceStepEditor`, `EnrollmentTable` |

### Analytics
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/analytics` | Overview, conversation trends, lead funnel, AI performance, export | `GET /analytics/*` | `MetricSummaryRow`, `ConversationTrendChart`, `LeadFunnelChart`, `AiPerformancePanel`, `ExportButton` |

### Settings (admin-gated except where noted)
| Route | Purpose | Key data | Key components |
|---|---|---|---|
| `/settings/organization` | Org name, industry, timezone, danger zone (delete org — owner only) | `GET/PATCH /auth/organizations/{id}` | `OrganizationForm`, `DangerZoneCard` |
| `/settings/whatsapp` | Connection status, connect/disconnect, template sync | `GET/POST /whatsapp/*` | `WhatsAppConnectionCard`, `TemplateList` |
| `/settings/calendar` | Google Calendar connection status, connect/disconnect | `GET/POST /calendar/*` | `CalendarConnectionCard` |
| `/settings/team` | Member list, invites, role management | `GET /auth/organizations/{id}/members`, `POST /invite` | `MemberTable`, `InviteDialog`, `RoleSelect` |
| `/settings/billing` | Plan, usage, invoices (post-MVP placeholder acceptable) | `GET /auth/organizations/{id}` | `PlanCard`, `UsageMeter` |
| `/settings/profile` | Personal profile (any `member`, not admin-gated) | `GET/PATCH /auth/me` | `ProfileForm`, `AvatarUploader` |

---

## 12.5 Route guard summary

```
middleware.ts
   ├─ no session            → (auth)/* allowed; everything else → /login
   ├─ session, no org       → /onboarding (org creation step) or /signup completion
   ├─ session + org,
   │  no WhatsApp connection → (dashboard)/* redirects to /onboarding
   │                           (dismissible — “skip for now” sets a cookie)
   └─ session + org + setup  → (dashboard)/* fully accessible, gated per-route by role
                               via server-side role checks mirroring API `require_role`
```

Admin-gated pages render their content behind a `RequireRole` server-side
check that redirects `agent`-role users to `/dashboard` with a toast
explaining the restriction — never a silent blank page.
