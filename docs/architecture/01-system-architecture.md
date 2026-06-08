# 1. System Architecture

## 1.1 Overview

WhatsAgent AI is a **multi-tenant SaaS** platform. Each business ("organization")
connects its WhatsApp Business Account (WABA), uploads its knowledge (PDFs,
DOCX, website URLs), and configures AI "employees" — an **AI Sales Agent** that
converses with customers/leads over WhatsApp, qualifies them, books
appointments, and a **Follow-Up Agent** that runs automated nurture sequences.
All activity rolls up into a CRM and an analytics dashboard.

## 1.2 High-level component map

```
                                ┌────────────────────────┐
                                │   Browser (business     │
                                │   owner / team)         │
                                └───────────┬────────────┘
                                            │ HTTPS
                                            ▼
                  ┌─────────────────────────────────────────────┐
                  │  Next.js 15 Frontend (Vercel)                │
                  │  - Marketing site, Auth pages, Dashboard      │
                  │  - Talks to Supabase Auth directly for        │
                  │    signup/login/reset                          │
                  │  - Talks to FastAPI for all business data      │
                  └───────────┬───────────────────┬──────────────┘
                              │ REST/JSON (JWT)    │ Supabase JS client
                              ▼                    ▼
                  ┌────────────────────────┐   ┌────────────────────────┐
                  │   FastAPI Backend       │   │  Supabase               │
                  │  (Render/Fly/Railway)   │◄──┤  - Auth (issues JWT)    │
                  │  - REST API layer       │   │  - Postgres + pgvector  │
                  │  - Webhook receivers    │   │  - Storage (KB files)   │
                  │  - AI orchestration     │   │  - Row Level Security   │
                  │  - Integration clients  │   └────────────────────────┘
                  └───────┬─────────┬───────┘
                          │         │
             ┌────────────┘         └─────────────┐
             ▼                                     ▼
  ┌────────────────────────┐           ┌────────────────────────────┐
  │  Background Workers     │           │  External Integrations      │
  │  (Celery + Redis)       │           │  - Meta WhatsApp Cloud API   │
  │  - Inbound msg pipeline │◄─────────►│  - OpenAI API                │
  │  - KB ingestion/embeds  │           │  - Anthropic Claude API      │
  │  - Follow-up scheduler  │           │  - Google Calendar API       │
  │  - Analytics rollups    │           └────────────────────────────┘
  └────────────────────────┘
```

## 1.3 Components

### Frontend — Next.js 15 (Vercel)
- App Router, TypeScript, Tailwind, shadcn/ui.
- Renders marketing pages, auth flows (backed by Supabase Auth), and the
  authenticated dashboard (Inbox, CRM, Knowledge Base, Agents, Appointments,
  Follow-ups, Analytics, Settings).
- Acts as a thin BFF: simple reads may go straight to Supabase (with RLS
  protecting tenant data); all business logic / AI / integrations go through
  FastAPI.

### Backend — FastAPI
- Stateless REST API (JWT-validated against Supabase) for all product
  features.
- Hosts the WhatsApp webhook receiver (must be a public, always-on HTTPS
  endpoint — not viable as a Vercel serverless function due to Meta's
  retry/latency expectations and the need for synchronous signature
  verification + fast ack).
- Owns the **AI orchestration layer**: a provider-agnostic interface over
  OpenAI and Claude, plus the RAG (retrieval-augmented generation) pipeline
  that grounds responses in the org's knowledge base.
- Owns integration clients: WhatsApp Cloud API, Google Calendar (OAuth2).
- Deployed as a container to a platform that supports long-running processes
  (Render / Fly.io / Railway / AWS ECS) — paired with a Celery worker + beat
  scheduler and Redis.

### Database & platform services — Supabase
- **Postgres** is the system of record (see `02-database-schema.md`).
- **pgvector** extension stores knowledge-base embeddings for semantic
  retrieval.
- **Storage** holds uploaded PDFs/DOCX (and any generated assets).
- **Auth** issues JWTs for signup/login/password-reset; the frontend talks to
  it directly, FastAPI validates tokens via Supabase's JWKS endpoint.
- **Row Level Security (RLS)** enforces tenant isolation at the database layer
  as defense-in-depth alongside application-level checks. The backend uses the
  Supabase service role for trusted server-side writes (e.g., webhook
  ingestion) and still scopes every query by `organization_id`.

### Background workers — Celery + Redis
Long-running or scheduled work is offloaded from the request/response cycle:
- Processing inbound WhatsApp messages and generating AI replies.
- Knowledge-base ingestion: text extraction, chunking, embeddings.
- Follow-up sequence scheduler (periodic "tick" via Celery beat).
- Analytics aggregation (daily rollups for fast dashboard reads).
- Calendar sync.

### External integrations
- **Meta WhatsApp Cloud API** — the messaging channel (send/receive,
  templates, media).
- **OpenAI API** and **Anthropic Claude API** — LLM completions and
  embeddings, behind a pluggable provider interface so an org (or a specific
  agent) can be configured to use either.
- **Google Calendar API** — OAuth2 connection per organization for
  availability checks and event creation (appointment booking).

## 1.4 Multi-tenancy model

- Signing up creates an **Organization** (the business).
- **Users** (Supabase `auth.users` + a `profiles` table) belong to
  organizations through `organization_members`, with a role
  (`owner` / `admin` / `agent`).
- Every tenant-scoped table carries an `organization_id`. RLS policies
  restrict rows to members of that organization; FastAPI additionally derives
  and enforces the active `organization_id` on every request (via a header or
  the user's default org).
- One WhatsApp Business connection and one Google Calendar connection per
  organization for the MVP (extensible to multiple numbers later).

## 1.5 Core data flows

### A. Inbound WhatsApp message → AI reply
1. Customer messages the business's WhatsApp number → Meta POSTs to
   `/webhooks/whatsapp`.
2. FastAPI verifies the `X-Hub-Signature-256` signature, immediately persists
   the raw event, upserts `contact` → `conversation` → `message`, and enqueues
   `process_inbound_message` (acking Meta within its timeout window).
3. A worker loads conversation history + runs RAG retrieval against the org's
   `knowledge_base_chunks` (pgvector similarity search), assembles a prompt
   using the org's configured **AI Sales Agent** persona, and calls the
   selected LLM provider (OpenAI or Claude).
4. The response is parsed for: a direct answer, lead-qualification data
   (name/phone/email/budget/location), and/or appointment intent.
5. The worker sends the reply via the WhatsApp Cloud API, stores the outbound
   `message`, upserts/updates the `lead` record, and writes a `lead_activity`
   entry. Dashboard counters update from this same event stream.

### B. Knowledge-base ingestion
1. User uploads a PDF/DOCX or submits a website URL from the dashboard.
2. The file is stored in Supabase Storage (or the URL is recorded); a
   `knowledge_base_documents` row is created with `status = pending`.
3. A worker extracts text (PDF/DOCX parsers, or HTML extraction for URLs),
   splits it into chunks, generates embeddings, and writes
   `knowledge_base_chunks` rows (with `vector` embeddings).
4. Status flips to `ready`; the RAG pipeline can now retrieve these chunks at
   query time. Failures are recorded with `status = failed` and a reason.

### C. Appointment booking
1. The AI agent detects booking intent mid-conversation and asks for a
   preferred time.
2. The backend checks the org's connected Google Calendar for free/busy slots
   and proposes options.
3. On confirmation, the backend creates a Google Calendar event, writes an
   `appointments` row linked to the `lead`/`contact`, and the agent sends a
   WhatsApp confirmation message.

### D. Follow-up sequences
1. Leads are enrolled into a `follow_up_sequence` based on configurable
   triggers (e.g., "new lead created", "no reply within 24h", "stage changed
   to Contacted").
2. A periodic worker scans `follow_up_enrollments` whose `next_run_at` is due,
   sends the next templated WhatsApp message, advances the step (or exits the
   sequence on reply / conversion / max-steps-reached), and reschedules
   `next_run_at`.

## 1.6 Why split frontend (Vercel) and backend (containers)?

Vercel serverless functions are a poor fit for: webhook endpoints that must
stay responsive under Meta's delivery/retry semantics, long-lived background
workers (embeddings generation, scheduled follow-ups), and processes that need
persistent connections to Redis/Postgres connection pools. FastAPI + Celery run
as containerized, always-on services; Next.js remains the presentation layer
and calls into FastAPI (and Supabase directly for simple authenticated reads).

## 1.7 Security & compliance

- **AuthN**: Supabase Auth issues JWTs (signup/login/password reset handled by
  Supabase; FastAPI never sees raw passwords). FastAPI validates JWTs against
  Supabase's JWKS and derives `user_id`.
- **AuthZ**: `organization_id` resolved per-request; RLS policies on every
  tenant table as a second layer (`organization_id IN (SELECT organization_id
  FROM organization_members WHERE user_id = auth.uid())`).
- **Secrets at rest**: WhatsApp access tokens and Google OAuth tokens are
  encrypted at rest (e.g., `pgcrypto` or application-level AES-GCM with a KMS
  key) and never exposed to the frontend.
- **Webhook integrity**: mandatory Meta signature verification; idempotent
  processing (dedupe by `whatsapp_message_id`) since Meta retries deliveries.
- **Rate limiting**: on public endpoints (webhook, auth-adjacent routes) and
  on outbound LLM/WhatsApp calls (cost & abuse control).
- **Auditability**: an `audit_logs` table records sensitive actions
  (connection changes, role changes, data exports).
