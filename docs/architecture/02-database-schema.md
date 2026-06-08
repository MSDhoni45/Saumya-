# 2. Database Schema (Supabase Postgres + pgvector)

This is an entity-level design spec — field names, types, and relationships —
to be turned into Alembic/SQL migrations during implementation. All
tenant-scoped tables carry `organization_id` and are protected by Row Level
Security (RLS) policies of the form:

```
organization_id IN (
  SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
)
```

Extensions required: `pgvector`, `pgcrypto` (for token encryption / UUIDs).

---

## 2.1 Identity & tenancy

### `organizations`
The business/tenant.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| name | text | |
| slug | text unique | URL-friendly identifier |
| industry | text | optional, helps tailor AI prompts |
| timezone | text | IANA tz, used for scheduling |
| subscription_plan | enum(`trial`,`starter`,`pro`,`enterprise`) | |
| subscription_status | enum(`active`,`past_due`,`canceled`) | |
| created_at / updated_at | timestamptz | |

### `profiles`
Extends Supabase `auth.users` (1:1, `id` shared).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK / FK → `auth.users.id` | |
| full_name | text | |
| avatar_url | text | |
| phone | text | |
| created_at / updated_at | timestamptz | |

### `organization_members`
Join table: which users belong to which orgs, and with what role.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK → organizations | |
| user_id | uuid FK → profiles | nullable until invite accepted |
| role | enum(`owner`,`admin`,`agent`) | |
| invited_email | text | for pending invites |
| status | enum(`invited`,`active`,`removed`) | |
| created_at | timestamptz | |

Unique: `(organization_id, user_id)`.

---

## 2.2 WhatsApp connection

### `whatsapp_connections`
One per organization (MVP).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK, unique | |
| waba_id | text | Meta WhatsApp Business Account ID |
| phone_number_id | text | Cloud API phone number ID |
| display_phone_number | text | |
| access_token_encrypted | bytea | encrypted at rest |
| webhook_verify_token | text | |
| status | enum(`connected`,`disconnected`,`error`) | |
| connected_at / last_synced_at | timestamptz | |

---

## 2.3 Conversations & messaging

### `contacts`
A WhatsApp end-user the org has talked to (raw identity; becomes a `lead` once qualified).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| whatsapp_phone | text | E.164 |
| name | text | from WhatsApp profile or captured |
| email | text | nullable, captured later |
| profile_attributes | jsonb | free-form extra data |
| created_at / updated_at | timestamptz | |

Unique: `(organization_id, whatsapp_phone)`.

### `conversations`
A message thread with a contact.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| contact_id | uuid FK → contacts | |
| status | enum(`open`,`snoozed`,`closed`) | |
| ai_enabled | boolean | toggled off on human takeover |
| assigned_agent_type | enum(`ai`,`human`) | who currently owns the thread |
| last_message_at | timestamptz | for inbox sorting |
| created_at / updated_at | timestamptz | |

### `messages`
Individual inbound/outbound messages.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| conversation_id | uuid FK → conversations | |
| organization_id | uuid FK | denormalized for RLS & query perf |
| direction | enum(`inbound`,`outbound`) | |
| sender_type | enum(`contact`,`ai_agent`,`human_agent`,`system`) | |
| whatsapp_message_id | text | Meta's message ID, used for idempotency |
| message_type | enum(`text`,`image`,`document`,`audio`,`video`,`template`,`interactive`) | |
| content | text | |
| media_url | text | nullable |
| status | enum(`sent`,`delivered`,`read`,`failed`) | from delivery webhooks |
| ai_metadata | jsonb | model used, tokens, latency, retrieved chunk IDs |
| created_at | timestamptz | |

Indexes: `(conversation_id, created_at)`, unique `(organization_id, whatsapp_message_id)`.

---

## 2.4 Knowledge base (RAG)

### `knowledge_base_documents`
Uploaded source material.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| source_type | enum(`pdf`,`docx`,`url`) | |
| title | text | |
| storage_path | text | Supabase Storage path (files) |
| source_url | text | for `url` type |
| status | enum(`pending`,`processing`,`ready`,`failed`) | |
| char_count / chunk_count | integer | populated post-processing |
| failure_reason | text | nullable |
| uploaded_by | uuid FK → profiles | |
| created_at / updated_at | timestamptz | |

### `knowledge_base_chunks`
Chunked text + embeddings for semantic search.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| document_id | uuid FK → knowledge_base_documents | |
| organization_id | uuid FK | denormalized — scoping retrieval queries |
| chunk_index | integer | order within document |
| content | text | |
| embedding | vector(1536) | dimension depends on embedding model |
| token_count | integer | |
| created_at | timestamptz | |

Indexes: `ivfflat`/`hnsw` on `embedding` (cosine distance) scoped via a
composite filter on `organization_id`; btree on `(organization_id, document_id)`.

---

## 2.5 AI agents & interaction logs

### `ai_agents`
Configurable "AI employees" per organization.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| type | enum(`sales`,`follow_up`,`support`) | |
| name | text | display name, e.g. "Aria — Sales Agent" |
| persona_prompt | text | system prompt / persona definition |
| model_provider | enum(`openai`,`anthropic`) | |
| model_name | text | e.g. `gpt-4.1`, `claude-sonnet-4-6` |
| temperature | numeric | |
| qualification_fields | jsonb | configurable: name, phone, email, budget, location, … |
| is_active | boolean | |
| created_at / updated_at | timestamptz | |

### `ai_interactions`
Observability/cost log for every LLM call.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| conversation_id | uuid FK, nullable | |
| agent_id | uuid FK → ai_agents | |
| provider / model | text | |
| prompt_tokens / completion_tokens | integer | |
| total_cost_usd | numeric | computed from provider pricing |
| latency_ms | integer | |
| request_prompt / response_text | jsonb/text | for debugging & evals |
| created_at | timestamptz | |

---

## 2.6 CRM (leads & pipeline)

### `leads`
A qualified/qualifying contact moving through the sales pipeline.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| contact_id | uuid FK → contacts, unique per org | |
| stage | enum(`new`,`qualified`,`contacted`,`won`,`lost`) | |
| name / phone / email / budget / location | text | captured qualification fields |
| source | enum(`whatsapp`,`manual`,`import`) | |
| assigned_to | uuid FK → profiles, nullable | |
| score | integer | optional lead-scoring |
| notes | text | |
| stage_changed_at | timestamptz | |
| created_at / updated_at | timestamptz | |

Index: `(organization_id, stage)`.

### `lead_activities`
Timeline/audit trail per lead.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| lead_id | uuid FK → leads | |
| organization_id | uuid FK | |
| activity_type | enum(`stage_change`,`note`,`message`,`appointment`,`system`) | |
| description | text | |
| metadata | jsonb | |
| created_by | uuid FK → profiles, nullable | null = AI/system-generated |
| created_at | timestamptz | |

---

## 2.7 Appointment booking

### `calendar_connections`
Google Calendar OAuth connection per organization.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK, unique | |
| provider | enum(`google`) | |
| google_account_email | text | |
| access_token_encrypted / refresh_token_encrypted | bytea | |
| calendar_id | text | |
| status | enum(`connected`,`disconnected`,`error`) | |
| connected_at | timestamptz | |

### `appointments`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| lead_id | uuid FK, nullable | |
| contact_id | uuid FK → contacts | |
| title | text | |
| starts_at / ends_at | timestamptz | |
| timezone | text | |
| status | enum(`scheduled`,`confirmed`,`completed`,`cancelled`,`no_show`) | |
| calendar_event_id | text | Google event ID |
| location / meeting_link | text | |
| created_via | enum(`ai_agent`,`manual`) | |
| created_at / updated_at | timestamptz | |

---

## 2.8 Follow-up agent

### `follow_up_sequences`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| name | text | |
| trigger | enum(`lead_created`,`no_response_24h`,`stage_changed`,`manual`) | |
| is_active | boolean | |
| created_at / updated_at | timestamptz | |

### `follow_up_steps`
Ordered messages within a sequence.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| sequence_id | uuid FK → follow_up_sequences | |
| step_order | integer | |
| delay_minutes | integer | offset from previous step / enrollment |
| message_template | text | supports `{{name}}`-style variables |
| channel | enum(`whatsapp`) | |
| created_at | timestamptz | |

### `follow_up_enrollments`
A lead's progress through a sequence.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| sequence_id | uuid FK | |
| lead_id | uuid FK | |
| contact_id | uuid FK | |
| current_step | integer | |
| status | enum(`active`,`completed`,`exited`,`paused`) | |
| next_run_at | timestamptz | scanned by the scheduler worker |
| enrolled_at / completed_at | timestamptz | |

Index: `(status, next_run_at)` (partial index where `status = 'active'`).

---

## 2.9 Analytics

### `analytics_daily_stats`
Pre-aggregated rollups for fast dashboard reads (refreshed by a worker).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| date | date | |
| conversations_count | integer | |
| new_leads_count | integer | |
| appointments_booked_count | integer | |
| ai_messages_sent | integer | |
| ai_messages_total | integer | denominator for AI response-rate |
| human_handoffs_count | integer | |

Unique: `(organization_id, date)`.

---

## 2.10 Cross-cutting

### `audit_logs`

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organization_id | uuid FK | |
| actor_id | uuid FK → profiles, nullable | |
| action | text | e.g. `whatsapp.connected`, `member.role_changed` |
| entity_type / entity_id | text / uuid | |
| metadata | jsonb | |
| created_at | timestamptz | |

---

## 2.11 Entity relationship summary

```
organizations 1──* organization_members *──1 profiles
organizations 1──1 whatsapp_connections
organizations 1──1 calendar_connections
organizations 1──* contacts 1──1 leads
organizations 1──* conversations *──1 contacts
conversations 1──* messages
organizations 1──* knowledge_base_documents 1──* knowledge_base_chunks
organizations 1──* ai_agents 1──* ai_interactions
organizations 1──* leads 1──* lead_activities
organizations 1──* appointments *──1 leads/contacts
organizations 1──* follow_up_sequences 1──* follow_up_steps
follow_up_sequences 1──* follow_up_enrollments *──1 leads
organizations 1──* analytics_daily_stats
```
