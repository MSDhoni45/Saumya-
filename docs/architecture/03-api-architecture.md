# 3. API Architecture (FastAPI)

Base path: **`/api/v1`**. JSON over HTTPS. OpenAPI docs auto-generated at
`/docs` (gated/disabled in production).

## 3.1 Auth model

- Signup, login, logout, and password reset are handled by **Supabase Auth**
  directly from the Next.js frontend (no custom password handling in our
  backend).
- Every authenticated request to FastAPI carries `Authorization: Bearer
  <supabase_jwt>`. A FastAPI dependency validates the token against Supabase's
  JWKS endpoint and resolves `user_id`.
- A second dependency resolves the **active organization** — from an
  `X-Org-Id` header (frontend sends the currently-selected org) — and verifies
  membership via `organization_members`. All downstream queries are scoped by
  this `organization_id`.
- Server-to-server operations (webhook ingestion, workers) use the Supabase
  **service role** key and explicitly pass/validate `organization_id`.

## 3.2 Conventions

- Response envelope: `{ "data": ..., "meta": {...} }` on success,
  `{ "error": { "code", "message", "details" } }` on failure.
- Pagination via `?page=&limit=` (or cursor for high-volume endpoints like
  messages) returned in `meta`.
- Filtering/search via query params (e.g. `?stage=qualified&search=acme`).
- All list/detail responses defined by Pydantic schemas mirroring the DB
  entities (see `02-database-schema.md`); request/response models are kept in
  `app/schemas/`.
- Idempotency: webhook and send-message endpoints dedupe on
  `whatsapp_message_id` / client-supplied idempotency keys.

## 3.3 Routers

### `auth` — org/profile bootstrap (passwords stay in Supabase)
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/bootstrap` | After Supabase signup, create the user's `profile` + first `organization` + owner membership |
| GET | `/auth/me` | Current user, profile, and list of organizations/roles |
| POST | `/auth/organizations` | Create an additional organization |
| POST | `/auth/invite` | Invite a teammate by email (creates pending `organization_members` row, sends invite) |
| POST | `/auth/invite/accept` | Accept an invite (links `user_id`) |

### `dashboard`
| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/summary` | Totals: conversations, leads generated, appointments booked, AI response rate (supports `?from=&to=`) |
| GET | `/dashboard/trends` | Time-series data for charts |

### `whatsapp` (connection management)
| Method | Path | Purpose |
|---|---|---|
| POST | `/whatsapp/connect` | Store WABA credentials (Embedded Signup result or manual token entry), subscribe webhook |
| GET | `/whatsapp/status` | Connection health |
| POST | `/whatsapp/disconnect` | Revoke/disable connection |
| POST | `/whatsapp/send` | Human-agent manual send (used from the inbox UI) |

### `webhooks` (public, signature-verified — not under `/api/v1`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/webhooks/whatsapp` | Meta webhook verification challenge |
| POST | `/webhooks/whatsapp` | Inbound message/status delivery; verifies `X-Hub-Signature-256`, persists, enqueues processing job, returns `200` immediately |

### `conversations`
| Method | Path | Purpose |
|---|---|---|
| GET | `/conversations` | List (filter: `status`, `assigned_agent_type`, `search`) |
| GET | `/conversations/{id}` | Detail |
| GET | `/conversations/{id}/messages` | Paginated message history |
| POST | `/conversations/{id}/messages` | Human agent sends a message (also used for "takeover") |
| PATCH | `/conversations/{id}` | Update status, toggle `ai_enabled` |

### `knowledge-base`
| Method | Path | Purpose |
|---|---|---|
| GET | `/knowledge-base/documents` | List with status |
| POST | `/knowledge-base/documents/upload` | Multipart PDF/DOCX upload → Supabase Storage, queues ingestion |
| POST | `/knowledge-base/documents/url` | Submit a website URL for ingestion |
| GET | `/knowledge-base/documents/{id}` | Detail incl. processing status |
| DELETE | `/knowledge-base/documents/{id}` | Remove document + its chunks |

### `agents`
| Method | Path | Purpose |
|---|---|---|
| GET | `/agents` | List configured AI agents (sales, follow-up, …) |
| GET | `/agents/{id}` | Detail |
| PUT | `/agents/{id}` | Update persona prompt, model/provider, temperature, qualification fields |
| POST | `/agents/{id}/test` | Sandbox: send a test message, see the agent's response without touching live conversations |

### `leads` (CRM)
| Method | Path | Purpose |
|---|---|---|
| GET | `/leads` | List/filter by `stage`, `assigned_to`, `search` |
| GET | `/leads/{id}` | Detail |
| POST | `/leads` | Manual creation |
| PATCH | `/leads/{id}` | Update fields / change `stage` (writes a `lead_activity`, may trigger follow-up enrollment) |
| GET | `/leads/{id}/activities` | Timeline |
| POST | `/leads/{id}/notes` | Add a note (creates a `lead_activity`) |

### `appointments` & `calendar`
| Method | Path | Purpose |
|---|---|---|
| GET | `/appointments` | List/filter by date range, status |
| POST | `/appointments` | Manual booking |
| PATCH | `/appointments/{id}` | Reschedule / cancel / mark complete |
| GET | `/calendar/connect` | Start Google OAuth flow (returns redirect URL) |
| GET | `/calendar/oauth/callback` | OAuth callback, stores encrypted tokens |
| GET | `/calendar/availability` | Free/busy slots for a date range |

### `follow-ups`
| Method | Path | Purpose |
|---|---|---|
| GET | `/follow-ups/sequences` | List sequences |
| POST | `/follow-ups/sequences` | Create sequence (+ steps) |
| PUT | `/follow-ups/sequences/{id}` | Update sequence/steps |
| GET | `/follow-ups/enrollments` | View active/past enrollments |
| POST | `/follow-ups/enrollments/{id}/pause` \| `/resume` \| `/exit` | Manual control over a lead's enrollment |

### `analytics`
| Method | Path | Purpose |
|---|---|---|
| GET | `/analytics/overview` | Headline metrics over a period |
| GET | `/analytics/conversations` | Volume/response-time trends |
| GET | `/analytics/leads-funnel` | Stage conversion funnel |
| GET | `/analytics/ai-performance` | AI response rate, handoff rate, cost |
| GET | `/analytics/export` | CSV export |

## 3.4 Background workers (Celery + Redis — not HTTP-exposed)

| Task | Trigger | Responsibility |
|---|---|---|
| `process_inbound_whatsapp_message` | enqueued by webhook handler | persist → retrieve KB context → call LLM → send reply → update lead/CRM |
| `ingest_knowledge_base_document` | enqueued on upload/URL submit | extract text → chunk → embed → store, update document status |
| `run_follow_up_scheduler` | Celery beat, every ~1 min | scan due `follow_up_enrollments`, send next step, advance/exit |
| `refresh_analytics_daily_stats` | Celery beat, hourly/daily | aggregate raw events into `analytics_daily_stats` |
| `sync_calendar_events` | periodic + on-demand | reconcile local `appointments` with Google Calendar |

## 3.5 AI orchestration layer (internal service, not an HTTP API)

`app/services/ai/orchestrator.py` exposes a provider-agnostic interface:

```
generate_reply(agent, conversation_history, retrieved_context) -> AgentResponse
```

Backed by pluggable providers (`openai_provider.py`, `anthropic_provider.py`)
selected per-agent (`ai_agents.model_provider`). The orchestrator is
responsible for: prompt assembly (persona + retrieved KB chunks + qualification
field instructions), calling the provider, parsing structured output (reply
text + extracted lead fields + detected intents like "wants to book"), and
logging every call to `ai_interactions` for cost/observability.

## 3.6 Rate limiting & resilience

- Public webhook endpoint: fast-ack (<5s) + queue-based processing; retries
  deduped by `whatsapp_message_id`.
- Outbound LLM and WhatsApp API calls: per-organization rate limits and
  exponential-backoff retries; circuit breaker around provider outages with
  fallback messaging ("we'll get back to you shortly" + human handoff).
- All write endpoints validate org membership and role (e.g., only
  `owner`/`admin` can change WhatsApp/Calendar connections or invite members).
