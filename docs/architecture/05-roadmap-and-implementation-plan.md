# 5. Development Roadmap & Implementation Plan

Estimates assume a small team (1–2 full-stack engineers, part-time design/PM).
Phases are mostly sequential due to data-model dependencies, but CRM/Analytics
UI work can start in parallel once the underlying schema for Phase 2/3 lands.
Total MVP estimate: **~16 weeks**.

---

## Phase 0 — Foundations (Week 1)

**Goal:** a working skeleton everyone can build on.

Tasks:
- Initialize monorepo (`apps/web`, `apps/api`, `infra`, `docs`).
- Provision Supabase project (Postgres, enable `pgvector`/`pgcrypto`, Auth, Storage).
- Scaffold Next.js 15 app (App Router, TS, Tailwind, shadcn/ui) and deploy a "hello world" to Vercel.
- Scaffold FastAPI app with health-check endpoint, Dockerfile, docker-compose for local Postgres+Redis.
- Set up Alembic migrations; create base tables: `organizations`, `profiles`, `organization_members`.
- Wire Supabase Auth into the frontend (no custom UI polish yet) and JWT validation in FastAPI.
- CI: lint + type-check + test pipelines for both apps.

**Acceptance criteria:** A logged-in user (via Supabase Auth) can hit an
authenticated FastAPI endpoint that returns their profile + organization,
end-to-end across Vercel ↔ FastAPI ↔ Supabase.

---

## Phase 1 — Auth + Dashboard shell (Week 2)

Tasks:
- Build signup / login / forgot-password / reset-password pages against Supabase Auth.
- `POST /auth/bootstrap`: create profile + organization + owner membership on first login.
- Authenticated dashboard shell: sidebar nav, topbar, organization switcher, empty-state pages for each module.
- `GET /dashboard/summary` returning real (initially zero/placeholder) counts wired to a KPI card UI.
- Team invite flow (`organization_members` invited/active states) — basic version.

**Acceptance criteria:** A new user can sign up, land in an empty dashboard
showing 4 KPI cards (conversations, leads, appointments, AI response rate),
and invite a teammate.

---

## Phase 2 — WhatsApp Cloud API integration (Weeks 3–4)

Tasks:
- `whatsapp_connections` table + `/whatsapp/connect` (manual token entry first; Embedded Signup as stretch), `/whatsapp/status`, `/whatsapp/disconnect`.
- Public `/webhooks/whatsapp` GET (verification challenge) and POST (signature-verified ingestion).
- Inbound pipeline: persist raw event → upsert `contact` → `conversation` → `message`; idempotent on `whatsapp_message_id`.
- `whatsapp_client.py`: send text messages, fetch media, mark-as-read.
- Inbox UI: conversation list (sorted by `last_message_at`), thread view, manual reply (`POST /conversations/{id}/messages`), AI on/off toggle (`ai_enabled`).
- Delivery status updates (sent/delivered/read) reflected on messages.

**Acceptance criteria:** A real WhatsApp message sent to the connected test
number appears in the inbox in real time (poll or websocket/SSE), and a human
reply sent from the dashboard is delivered to the customer's WhatsApp.

---

## Phase 3 — Knowledge Base + AI Sales Agent (Weeks 5–7)

Tasks:
- `knowledge_base_documents` / `knowledge_base_chunks` tables; Supabase Storage bucket for uploads.
- `POST /knowledge-base/documents/upload` (PDF/DOCX) and `/url` endpoints; KB management UI (list, status, delete).
- Worker pipeline: extraction (PDF/DOCX/HTML) → chunking → embeddings → storage; status transitions `pending → processing → ready/failed`.
- `rag.py`: pgvector similarity search scoped by `organization_id`.
- `ai_agents` table + agent config UI (persona prompt, provider/model, temperature, qualification fields).
- AI orchestration layer (`orchestrator.py`, `openai_provider.py`, `anthropic_provider.py`) with structured output: reply text + extracted qualification fields + detected intents.
- Hook orchestration into the inbound pipeline: when `ai_enabled = true`, generate and send AI replies automatically; log every call to `ai_interactions`.
- Agent "test sandbox" (`POST /agents/{id}/test`).

**Acceptance criteria:** After uploading a PDF describing the business, a test
WhatsApp message asking a relevant question receives an accurate, grounded AI
reply within a few seconds, and the call is logged with token/cost metadata.

---

## Phase 4 — CRM (Weeks 8–9)

Tasks:
- `leads` / `lead_activities` tables; auto-create/update a `lead` when the AI extracts qualification data (name/phone/email/budget/location) from a conversation.
- CRM UI: kanban board across stages (`new → qualified → contacted → won → lost`), drag-to-change-stage, lead detail panel with activity timeline and notes.
- `GET/POST/PATCH /leads`, `/leads/{id}/activities`, `/leads/{id}/notes`.
- Manual lead creation/assignment; role-based visibility (e.g., agents see only assigned leads, admins see all — configurable).

**Acceptance criteria:** A qualifying WhatsApp conversation automatically
produces a lead card on the CRM board with captured fields; manually dragging
it across stages records an activity and timestamps the transition.

---

## Phase 5 — Appointment Booking (Weeks 10–11)

Tasks:
- `calendar_connections` table; Google OAuth2 flow (`/calendar/connect`, `/calendar/oauth/callback`), encrypted token storage + refresh handling.
- `calendar_service.py`: free/busy lookup, event creation/update/cancellation.
- Extend the AI orchestration to detect booking intent, propose available slots, and confirm bookings conversationally.
- `appointments` table + `/appointments` CRUD; Appointments UI (calendar/list view, manual booking, reschedule/cancel).
- WhatsApp confirmation/reminder messages tied to appointment status changes.

**Acceptance criteria:** A WhatsApp conversation can end with a confirmed
appointment that appears on the connected Google Calendar and in the
dashboard's Appointments view, with a confirmation message sent to the
customer.

---

## Phase 6 — Follow-Up Agent (Weeks 12–13)

Tasks:
- `follow_up_sequences` / `follow_up_steps` / `follow_up_enrollments` tables.
- Sequence builder UI (ordered steps, delay configuration, message templates with variables).
- Enrollment rules engine: triggers on lead creation, no-response timeout, stage changes; manual enrollment.
- `run_follow_up_scheduler` Celery-beat task: scans due enrollments, sends next step via WhatsApp, advances/exits sequences (on reply, conversion, or completion), reschedules `next_run_at`.
- Pause/resume/exit controls in the UI and API.

**Acceptance criteria:** A lead with no reply for 24 hours automatically
receives a configured follow-up message at the scheduled time, and replying
exits them from the sequence.

---

## Phase 7 — Analytics Dashboard (Week 14)

Tasks:
- `analytics_daily_stats` table + `refresh_analytics_daily_stats` rollup worker.
- `/analytics/*` endpoints: overview, conversation trends, lead funnel, AI performance (response rate, handoff rate, cost), CSV export.
- Charting UI (conversations over time, funnel chart, AI response-rate gauge, cost breakdown).

**Acceptance criteria:** The analytics page renders accurate charts for a
date range, matching the underlying raw data, and supports CSV export.

---

## Phase 8 — Hardening & Launch Prep (Weeks 15–16)

Tasks:
- RLS policy audit across all tenant tables; penetration-style review of auth/org-scoping.
- Rate limiting (webhook, LLM calls, WhatsApp sends) and retry/circuit-breaker logic.
- Observability: structured logging, error monitoring (e.g., Sentry), basic uptime/alerting on webhook + worker health.
- Load-test the webhook ingestion path (Meta retry behavior, burst traffic).
- Onboarding flow polish (guided setup: connect WhatsApp → upload KB → configure agent → go live).
- Staging environment + deployment pipelines for `apps/web` (Vercel) and `apps/api` (container platform); secrets management.
- (If in scope) basic billing/plan gating.

**Acceptance criteria:** A new business can go from signup to a live,
AI-answering WhatsApp number in under 15 minutes via the guided onboarding,
with monitoring/alerts in place for the on-call engineer.

---

## Cross-cutting / ongoing throughout all phases

- **Testing:** unit tests for services (especially AI orchestration, RAG
  retrieval, follow-up scheduling logic) and integration tests for API routers;
  contract tests against the WhatsApp webhook payload shapes.
- **Type-safety bridge:** generate TS types from the FastAPI OpenAPI schema
  into the frontend on every backend schema change.
- **Prompt iteration:** maintain a versioned prompt library
  (`services/ai/prompts/`) and an evaluation set of sample conversations to
  regression-test agent behavior as prompts evolve.
- **Cost tracking:** every LLM call logged to `ai_interactions` from day one
  (Phase 3 onward) so cost-per-conversation is visible before scaling traffic.

---

## Suggested team parallelization (if >1 engineer)

| Track | Owns |
|---|---|
| Platform/Backend | Phases 0, 2 (webhook + messaging core), 3 (AI orchestration + RAG), 8 (hardening) |
| Product/Frontend | Phase 1 (dashboard shell), Inbox UI (parallel with backend Phase 2), CRM/Appointments/Follow-ups/Analytics UIs (parallel with their respective backend phases) |
| Integrations | Phase 5 (Google Calendar), WhatsApp Embedded Signup stretch goal, billing (Phase 8) |

This lets UI work for a phase begin once its data model and API contracts are
defined (even before the backend logic is fully built), shortening the
critical path.
