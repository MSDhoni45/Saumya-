# 10. Backend Implementation Order

A granular, dependency-ordered build sequence for `apps/api`. This refines
the phase-level roadmap in `05-roadmap-and-implementation-plan.md` into the
concrete order backend work should happen in — each step only depends on
steps above it, so a single engineer can move straight down the list, and a
team can fan out once the marked "fan-out points" are reached.

## Step 1 — Project skeleton & wiring
1. `pyproject.toml`/`requirements.txt`, Dockerfile, `docker-compose.yml`
   (Postgres+pgvector, Redis, api, worker).
2. `app/core/config.py` (Settings via pydantic-settings) + `.env.example`.
3. `app/main.py` app factory + `lifespan` (DB engine, Redis pool, HTTP clients).
4. `/healthz`, `/readyz`.
5. Logging + request-ID middleware + exception handler skeleton (`app/core/errors.py`).
6. CI: lint (ruff), type-check (mypy/pyright), test runner wired to an empty suite.

**Exit check:** `docker compose up` serves `/healthz` → `200`.

## Step 2 — Database layer
1. `app/db/session.py` (async engine + session factory), `app/db/base.py`.
2. SQLAlchemy models in `app/models/` mirroring every table from the
   `supabase/migrations/*` schema (one module per domain, matching migration
   groupings: `organizations.py`, `messaging.py`, `knowledge_base.py`, etc.).
3. Confirm models load against the already-applied Supabase schema (point
   `DATABASE_URL` at the Supabase Postgres connection string — migrations are
   the source of truth; SQLAlchemy models are a typed mirror, not a
   migration-generation tool).
4. Pydantic schemas in `app/schemas/` for the entities needed by Step 3
   (profile, organization, membership) — extend per-domain as later steps land.

**Exit check:** a script can open a session and `SELECT` from `organizations`.

## Step 3 — Auth dependency chain & org bootstrap
1. `app/core/security.py`: JWKS fetch/cache, `get_current_user`,
   `get_current_organization`, `require_role`.
2. `app/api/v1/auth.py`: `/auth/bootstrap`, `/auth/me`, `/auth/organizations`,
   member listing, invites (`/invite`, `/invites/accept`, member
   PATCH/DELETE).
3. `app/services/` — org/membership service backing the above (slug
   generation, idempotent bootstrap, invite matching).
4. Integration tests: a fake/overridden `get_current_user` injects a known
   user; verify bootstrap idempotency, role-gated 403s, invite acceptance.

**Exit check:** an authenticated request to `/auth/me` returns the right
shape end-to-end through Vercel ↔ FastAPI ↔ Supabase (manual or scripted).

## Step 4 — Dashboard shell endpoint
1. `app/api/v1/dashboard.py`: `/dashboard/summary` returning real counts from
   already-existing tables (will be all zeros until Step 5+ produces data —
   that's fine, it proves the query/response shape).

**Exit check:** dashboard cards render real (zero) values from a live query.

---
> **Fan-out point A**: Steps 1–4 establish the platform. From here, WhatsApp
> messaging (Step 5) is the critical path — almost everything depends on
> conversations/contacts existing — but knowledge-base scaffolding (Step 6,
> minus the "hook into pipeline" sub-step) can start in parallel.
---

## Step 5 — WhatsApp connection & messaging core
1. `services/whatsapp_client.py`: Graph API wrapper (validate token, send
   text, mark-as-read, media up/download) with retry/backoff and the
   24-hour-window template fallback described in
   `09-whatsapp-integration-architecture.md §9.4`.
2. `app/api/v1/whatsapp.py`: `/whatsapp/connect`, `/status`, `/disconnect`,
   `/sync-templates`, `/send`.
3. `app/webhooks/whatsapp.py`: GET verification challenge, POST receiver with
   signature verification, payload parsing, organization resolution by
   `phone_number_id`, raw-event persistence, per-message task enqueueing.
   **Returns 200 fast — no synchronous processing.**
4. `workers/tasks/inbound_messages.py`: `process_inbound_whatsapp_message`
   — upsert contact/conversation/message, mark-as-read, status-update routing.
   (AI reply generation is stubbed/no-op here — wired in Step 7.)
5. `app/api/v1/conversations.py`: list/detail/messages/manual-send/PATCH/assign.
6. Contract tests against recorded Meta webhook payload fixtures (text, media,
   status, error, duplicate-delivery).

**Exit check:** a message sent to the connected test WhatsApp number appears
in `GET /conversations/{id}/messages`, and a reply sent via
`POST /conversations/{id}/messages` is delivered to the customer's phone.

## Step 6 — Knowledge base ingestion
1. Supabase Storage bucket + signed-upload handling.
2. `app/api/v1/knowledge_base.py`: upload, URL submission, list/detail/delete,
   reprocess, search (debug endpoint).
3. `services/knowledge_base/extractors.py` (PDF via `pypdf`, DOCX via
   `python-docx`, URL via `trafilatura`/`readability`) and `chunking.py`
   (token-aware splitting + embedding calls).
4. `workers/tasks/knowledge_base.py`: `ingest_knowledge_base_document` —
   extract → chunk → embed → store chunks → flip document status.
5. `services/ai/rag.py`: pgvector cosine-similarity retrieval scoped by
   `organization_id`, used by both `/knowledge-base/search` and the AI
   pipeline (Step 7).

**Exit check:** uploading a PDF transitions `pending → processing → ready`
with a non-zero `chunk_count`, and `/knowledge-base/search` returns relevant
chunks for a test query.

## Step 7 — AI orchestration & the Sales Agent
1. `app/models`/`schemas` + `app/api/v1/agents.py`: agent CRUD, persona/model
   config, `/agents/{id}/test` sandbox.
2. `services/ai/openai_provider.py`, `anthropic_provider.py`: thin,
   interchangeable completion + structured-output wrappers; provider fakes
   for tests.
3. `services/ai/orchestrator.py`: prompt assembly (persona + qualification
   instructions + retrieved chunks + history), provider dispatch, structured
   parsing (`reply_text`, `extracted_fields`, `detected_intent`), logging to
   `ai_interactions`.
4. `services/ai/prompts/`: versioned persona/system-prompt templates +
   an evaluation fixture set (sample conversations with expected extractions).
5. Wire the orchestrator into `process_inbound_whatsapp_message` (the stub
   from Step 5): when `ai_enabled`, generate → log → send reply.
6. Human-takeover triggers: low-confidence / explicit handoff requests flip
   `ai_enabled = false` and notify the team.

**Exit check:** after uploading a knowledge-base doc and configuring a sales
agent persona, a live WhatsApp question receives an accurate, grounded reply,
logged with token/cost data in `ai_interactions`.

---
> **Fan-out point B**: With messages → AI → structured extraction flowing,
> CRM (Step 8), Appointments (Step 9), and Follow-ups (Step 10) can be built
> largely in parallel — they each consume `extracted_fields`/`detected_intent`
> independently and don't depend on each other.
---

## Step 8 — CRM (leads)
1. `services/crm_service.py`: `upsert_lead_from_conversation`, stage
   transitions (+ `lead_activities` writes), assignment, notes.
2. `app/api/v1/leads.py`: full CRUD, activities, notes, filtering.
3. Hook `crm_service.upsert_lead_from_conversation` into the AI pipeline's
   `extracted_fields` handling (Step 7.5 side effect).

**Exit check:** a qualifying conversation auto-creates/updates a `leads` row
with an activity-timeline entry; manual stage changes via the API persist and
timestamp correctly (verifying the DB trigger from migration 07).

## Step 9 — Appointment booking
1. `services/calendar_service.py`: Google OAuth2 flow (authorization URL,
   callback/token exchange, encrypted storage, refresh handling), free/busy
   lookup, event create/update/cancel.
2. `app/api/v1/appointments.py` + calendar connection routes
   (`/calendar/connect`, `/oauth/callback`, `/status`, `/disconnect`,
   `/availability`).
3. Extend the orchestrator (Step 7) to handle `detected_intent.wants_to_book`:
   propose slots from `calendar_service.availability`, confirm, create the
   appointment + calendar event, send a WhatsApp confirmation.

**Exit check:** a conversation ending in "yes, book Tuesday at 3pm" produces
a confirmed `appointments` row, a Google Calendar event, and a WhatsApp
confirmation message.

## Step 10 — Follow-up agent
1. `services/follow_up_service.py`: enrollment rules (trigger evaluation on
   lead-create / stage-change / no-response), step progression, exit
   conditions.
2. `app/api/v1/follow_ups.py`: sequence CRUD (with nested step replacement),
   enrollment listing, pause/resume/exit.
3. `workers/tasks/follow_ups.py` + Celery beat schedule:
   `run_follow_up_scheduler` — scans `follow_up_enrollments` where
   `status='active' AND next_run_at <= now()` (the partial index from
   migration 09 makes this scan cheap), sends the step's message (via
   `whatsapp_client`, respecting the 24h template-fallback rule), advances
   `current_step`/`next_run_at` or marks `completed`/`exited`.
4. Reply-triggered exit: the inbound pipeline (Step 5/7) checks for an active
   enrollment on reply and exits it.

**Exit check:** a lead with no reply for the configured delay receives the
next sequence message at the scheduled time; replying exits them from the
sequence (verified via `follow_up_enrollments.status`).

## Step 11 — Analytics
1. `workers/tasks/analytics.py`: `refresh_analytics_daily_stats` — aggregates
   the day's conversations/leads/appointments/AI messages into
   `analytics_daily_stats` (upsert on `(organization_id, date)`).
2. `app/api/v1/analytics.py`: overview, conversation trends, leads funnel,
   AI performance, CSV export.

**Exit check:** analytics endpoints return values that reconcile with the raw
tables for a known date range; CSV export downloads and parses correctly.

## Step 12 — Hardening
1. Rate limiting (Redis token buckets: webhook, outbound WhatsApp, LLM calls,
   exports) and the `ExternalServiceError` circuit breaker around providers.
2. Structured logging → error monitoring (Sentry) wiring; Celery
   failure/retry signal hooks.
3. Load test the webhook path (burst + Meta-retry simulation) against the
   idempotency guarantees from Step 5.
4. Security pass: confirm every router path enforces the right
   `require_role`, re-audit RLS policies against the final query patterns,
   verify token-encryption round-trips (`whatsapp_connections`,
   `calendar_connections`).
5. Deployment: container build pipeline, staging environment, secrets
   management, `celery beat` scheduler deployment alongside the worker.

**Exit check:** the system survives a simulated burst of duplicate webhook
deliveries without double-processing, all admin-only routes reject `agent`
role tokens with `403`, and a fresh deploy passes `/readyz`.

---

## Suggested fan-out for a 2-engineer team

| Engineer A (messaging/AI core) | Engineer B (product surfaces) |
|---|---|
| Steps 1–2 (shared setup, pair) | — |
| Step 3 (auth) | Step 4 (dashboard shell, parallel once Step 2 lands) |
| Step 5 (WhatsApp + messaging) | Step 6 (knowledge base, parallel — independent until the RAG hook) |
| Step 7 (AI orchestration) | continues Step 6, then starts Step 8 (CRM) once `extracted_fields` shape is agreed |
| Step 9 (appointments) | Step 10 (follow-ups) — both consume Step 7 outputs independently |
| Step 12 (hardening, messaging side) | Step 11 (analytics) then Step 12 (hardening, product side) |

Agreeing the **shape of `extracted_fields`/`detected_intent`** (Step 7) early
— even before the orchestrator is fully implemented — is what unlocks Steps
8–10 to proceed in parallel against a stable contract.
