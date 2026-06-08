# 7. Complete API Endpoint Reference

Base path `/api/v1` (JWT-authenticated unless noted). Webhook routes are
mounted separately at `/webhooks/*` (public, signature-verified). Auth
columns: **Auth** = `none` (public), `user` (valid Supabase JWT), `member`
(JWT + active org membership), `admin` (JWT + `owner`/`admin` role).

Response envelope: `{ "data": ..., "meta": {...} }` on 2xx,
`{ "error": { "code", "message", "details" } }` on 4xx/5xx.

---

## 7.1 Auth & organization bootstrap — `/auth`

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| POST | `/auth/bootstrap` | user | `{ org_name }` | `{ organization, membership }` | Idempotent first-login hook: creates `profiles` row (if missing), an `organizations` row, and an `owner` `organization_members` row |
| GET | `/auth/me` | user | — | `{ profile, organizations: [{ organization, role }] }` | Drives the org switcher |
| PATCH | `/auth/me` | user | `{ full_name?, phone?, avatar_url? }` | `{ profile }` | Update own profile |
| POST | `/auth/organizations` | user | `{ name, industry?, timezone? }` | `{ organization, membership }` | Create an additional org (caller becomes owner) |
| GET | `/auth/organizations/{org_id}/members` | member | — | `{ members: [...] }` | List team members & pending invites |
| POST | `/auth/organizations/{org_id}/invite` | admin | `{ email, role }` | `{ membership }` | Creates a pending `organization_members` row, sends invite email (Supabase Auth invite or custom email) |
| POST | `/auth/invites/accept` | user | `{ invite_token }` | `{ membership }` | Links the authenticated user to a pending invite |
| PATCH | `/auth/organizations/{org_id}/members/{member_id}` | admin | `{ role?, status? }` | `{ membership }` | Change role / remove member |
| DELETE | `/auth/organizations/{org_id}/members/{member_id}` | admin | — | `204` | Remove a member |

> Signup, login, logout, and password reset are performed by the **frontend
> directly against Supabase Auth** (no custom backend endpoints — see
> `08-authentication-flow.md`). `/auth/bootstrap` is the one custom hook,
> called immediately after a user's first successful sign-in.

---

## 7.2 Dashboard — `/dashboard`

| Method | Path | Auth | Request (query) | Response |
|---|---|---|---|---|
| GET | `/dashboard/summary` | member | `from?, to?` (ISO dates, default: last 30 days) | `{ conversations_count, leads_generated, appointments_booked, ai_response_rate, deltas: {...} }` |
| GET | `/dashboard/trends` | member | `metric, from?, to?, granularity?` (`day`\|`week`) | `{ series: [{ date, value }] }` |
| GET | `/dashboard/recent-activity` | member | `limit?` | `{ items: [...] }` | Latest conversations/leads/appointments for the activity feed |

---

## 7.3 WhatsApp connection — `/whatsapp`

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| POST | `/whatsapp/connect` | admin | `{ waba_id, phone_number_id, access_token }` | `{ connection }` | Validates token against Graph API, encrypts & stores it, registers/subscribes the webhook |
| GET | `/whatsapp/status` | member | — | `{ connection: {...} \| null }` | Connection health incl. `last_synced_at` |
| POST | `/whatsapp/disconnect` | admin | — | `204` | Unsubscribes webhook, marks `disconnected` |
| POST | `/whatsapp/sync-templates` | admin | — | `{ templates: [...] }` | Pulls approved message templates from Meta for use in follow-ups |
| POST | `/whatsapp/send` | member | `{ conversation_id, content, message_type? }` | `{ message }` | Human-agent manual send from the inbox (also flips `assigned_agent_type` to `human` if needed) |

---

## 7.4 Webhooks — `/webhooks` (public, no `/api/v1` prefix)

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/webhooks/whatsapp` | none | `hub.mode, hub.verify_token, hub.challenge` (query) | plain-text challenge | Meta's webhook verification handshake |
| POST | `/webhooks/whatsapp` | none (signature-verified) | Meta event payload | `200 OK` (empty) | Verifies `X-Hub-Signature-256`, persists raw event, upserts contact/conversation/message, enqueues `process_inbound_whatsapp_message`; **must ack within Meta's timeout regardless of downstream processing outcome** |
| GET | `/webhooks/google-calendar` | none | — | `200 OK` | Push-notification channel renewal endpoint (optional, post-MVP) |

---

## 7.5 Conversations & inbox — `/conversations`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/conversations` | member | `status?, assigned_agent_type?, search?, page?, limit?` | `{ items: [...], meta: { page, total } }` |
| GET | `/conversations/{id}` | member | — | `{ conversation, contact, lead? }` |
| GET | `/conversations/{id}/messages` | member | `before?, limit?` (cursor pagination) | `{ items: [...], meta: { next_cursor } }` |
| POST | `/conversations/{id}/messages` | member | `{ content, message_type? }` | `{ message }` |
| PATCH | `/conversations/{id}` | member | `{ status?, ai_enabled? }` | `{ conversation }` | Toggling `ai_enabled = false` is the "human takeover" switch |
| POST | `/conversations/{id}/assign` | member | `{ assignee_id }` | `{ conversation }` | Assigns a human teammate to the thread |

---

## 7.6 Knowledge base — `/knowledge-base`

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/knowledge-base/documents` | member | `status?, source_type?, page?` | `{ items: [...] }` |
| POST | `/knowledge-base/documents/upload` | member | multipart: `file` (PDF/DOCX), `title?` | `{ document }` (status `pending`) | Streams to Supabase Storage, enqueues `ingest_knowledge_base_document` |
| POST | `/knowledge-base/documents/url` | member | `{ url, title? }` | `{ document }` | Enqueues ingestion of a website URL |
| GET | `/knowledge-base/documents/{id}` | member | — | `{ document }` | Includes `status`, `chunk_count`, `failure_reason` |
| DELETE | `/knowledge-base/documents/{id}` | admin | — | `204` | Cascades to its chunks |
| POST | `/knowledge-base/documents/{id}/reprocess` | admin | — | `{ document }` | Re-queues a `failed` document |
| POST | `/knowledge-base/search` | member | `{ query, top_k? }` | `{ results: [{ chunk, score, document }] }` | Debug/inspector endpoint — runs the same retrieval the AI agent uses |

---

## 7.7 AI agents — `/agents`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/agents` | member | — | `{ items: [...] }` |
| GET | `/agents/{id}` | member | — | `{ agent }` |
| PUT | `/agents/{id}` | admin | `{ name?, persona_prompt?, model_provider?, model_name?, temperature?, qualification_fields?, is_active? }` | `{ agent }` |
| POST | `/agents/{id}/test` | admin | `{ message, conversation_history? }` | `{ reply, extracted_fields, retrieved_chunks, usage }` | Sandbox call — runs the orchestrator without touching live data; logged to `ai_interactions` with a `sandbox` flag |

---

## 7.8 CRM / leads — `/leads`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/leads` | member | `stage?, assigned_to?, search?, page?, limit?` | `{ items: [...], meta: {...} }` |
| GET | `/leads/{id}` | member | — | `{ lead, contact, conversation? }` |
| POST | `/leads` | member | `{ contact_id?, name, phone?, email?, budget?, location?, source? }` | `{ lead }` | Creates `contact` if `contact_id` omitted |
| PATCH | `/leads/{id}` | member | `{ stage?, name?, phone?, email?, budget?, location?, assigned_to?, notes? }` | `{ lead }` | Stage changes write a `lead_activities` row and may trigger follow-up enrollment rules |
| DELETE | `/leads/{id}` | admin | — | `204` |
| GET | `/leads/{id}/activities` | member | `page?` | `{ items: [...] }` |
| POST | `/leads/{id}/notes` | member | `{ note }` | `{ activity }` |

---

## 7.9 Appointments & calendar — `/appointments`, `/calendar`

| Method | Path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| GET | `/appointments` | member | `from?, to?, status?, page?` | `{ items: [...] }` |
| GET | `/appointments/{id}` | member | — | `{ appointment }` |
| POST | `/appointments` | member | `{ contact_id, lead_id?, title, starts_at, ends_at, timezone?, location? }` | `{ appointment }` | Creates the Google Calendar event if connected |
| PATCH | `/appointments/{id}` | member | `{ starts_at?, ends_at?, status?, location? }` | `{ appointment }` | Reschedule/cancel/complete; syncs the calendar event |
| DELETE | `/appointments/{id}` | admin | — | `204` |
| GET | `/calendar/connect` | admin | — | `{ authorization_url }` | Starts Google OAuth2 flow |
| GET | `/calendar/oauth/callback` | admin | `code, state` (query) | redirect to dashboard | Exchanges code for tokens, encrypts & stores them |
| GET | `/calendar/status` | member | — | `{ connection: {...} \| null }` |
| POST | `/calendar/disconnect` | admin | — | `204` |
| GET | `/calendar/availability` | member | `from, to, duration_minutes?` | `{ slots: [{ starts_at, ends_at }] }` | Used by both the UI and the AI agent's booking flow |

---

## 7.10 Follow-up agent — `/follow-ups`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/follow-ups/sequences` | member | `is_active?` | `{ items: [...] }` |
| GET | `/follow-ups/sequences/{id}` | member | — | `{ sequence, steps: [...] }` |
| POST | `/follow-ups/sequences` | admin | `{ name, trigger, steps: [{ step_order, delay_minutes, message_template, channel? }] }` | `{ sequence }` |
| PUT | `/follow-ups/sequences/{id}` | admin | `{ name?, trigger?, is_active?, steps? }` | `{ sequence }` | Replaces the step list transactionally |
| DELETE | `/follow-ups/sequences/{id}` | admin | — | `204` |
| GET | `/follow-ups/enrollments` | member | `sequence_id?, status?, lead_id?, page?` | `{ items: [...] }` |
| POST | `/follow-ups/enrollments` | admin | `{ sequence_id, lead_id }` | `{ enrollment }` | Manual enrollment |
| POST | `/follow-ups/enrollments/{id}/pause` | admin | — | `{ enrollment }` |
| POST | `/follow-ups/enrollments/{id}/resume` | admin | — | `{ enrollment }` |
| POST | `/follow-ups/enrollments/{id}/exit` | admin | — | `{ enrollment }` |

---

## 7.11 Analytics — `/analytics`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/analytics/overview` | member | `from?, to?` | `{ totals: {...}, comparisons: {...} }` |
| GET | `/analytics/conversations` | member | `from?, to?, granularity?` | `{ series: [...] }` |
| GET | `/analytics/leads-funnel` | member | `from?, to?` | `{ stages: [{ stage, count, conversion_rate }] }` |
| GET | `/analytics/ai-performance` | member | `from?, to?` | `{ response_rate, avg_latency_ms, handoff_rate, total_cost_usd, by_model: [...] }` |
| GET | `/analytics/export` | admin | `from?, to?, format=csv` | streamed CSV file |

---

## 7.12 System / ops

| Method | Path | Auth | Response | Notes |
|---|---|---|---|---|
| GET | `/healthz` | none | `{ status: "ok" }` | Liveness probe |
| GET | `/readyz` | none | `{ status: "ok", db: "ok", redis: "ok" }` | Readiness probe (checks DB + Redis connectivity) |
| GET | `/docs`, `/openapi.json` | admin (prod) / none (dev) | OpenAPI UI/schema | Disabled or auth-gated outside development |

---

## 7.13 Pagination, filtering & sorting conventions

- Offset pagination: `?page=1&limit=25` → `meta: { page, limit, total, total_pages }`.
- Cursor pagination (high-volume, e.g. messages): `?before=<cursor>&limit=50` → `meta: { next_cursor }`.
- Sorting: `?sort=-created_at` (`-` prefix = descending); each endpoint documents its allowed sort fields.
- Search: `?search=<term>` performs an `ILIKE`/trigram match on the relevant text fields (name, phone, email).
- Date filters: `from`/`to` as ISO-8601 dates; default ranges documented per endpoint.
