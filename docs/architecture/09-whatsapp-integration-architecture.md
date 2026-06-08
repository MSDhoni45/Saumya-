# 9. WhatsApp Cloud API Integration Architecture

WhatsApp is the product's primary channel: every inbound customer message
must be received reliably, every AI/human reply must be sent reliably, and
the whole pipeline must survive Meta's retry/latency semantics. This section
details connection setup, the inbound pipeline, the outbound pipeline, and
failure handling.

## 9.1 Components

```
Meta WhatsApp Cloud API  ◄──────────────►  whatsapp_client.py (httpx async client)
        │ webhook (HTTPS POST)                       ▲
        ▼                                            │ send/media/template calls
app/webhooks/whatsapp.py  (public receiver)          │
        │ enqueue                                    │
        ▼                                            │
Celery: process_inbound_whatsapp_message  ───────────┘
        │
        ├─► persist message/contact/conversation
        ├─► RAG retrieval + AI orchestration (if ai_enabled)
        ├─► CRM update (lead extraction)
        └─► send reply via whatsapp_client.py
```

## 9.2 Connecting a WhatsApp Business Account

MVP supports **manual token entry** (business owner pastes their WABA ID,
Phone Number ID, and a permanent access token generated in Meta Business
Manager); **Embedded Signup** (Meta's hosted OAuth-like flow that provisions
everything programmatically) is a fast-follow enhancement noted but not
required for MVP.

```
Admin → POST /api/v1/whatsapp/connect { waba_id, phone_number_id, access_token }
        │
        ▼
FastAPI (whatsapp_service.connect):
   1. Calls Graph API GET /{phone_number_id} with the token to validate it
      and fetch display_phone_number
   2. Encrypts access_token (AES-GCM, app-level key) → access_token_encrypted
   3. Generates a random webhook_verify_token, stores it
   4. Calls Graph API POST /{waba_id}/subscribed_apps to subscribe the
      app to this WABA's webhooks
   5. Upserts whatsapp_connections (status = 'connected', connected_at = now())
   6. Writes audit_logs ('whatsapp.connected')
        │
        ▼
Returns { connection } — UI shows "Connected" with the display number
```

The org then configures the webhook callback URL
(`https://api.whatsagent.ai/webhooks/whatsapp`) and the generated
`webhook_verify_token` in the Meta App dashboard (one-time setup per app —
documented in the onboarding guide; for a single shared Meta App serving all
tenants, routing to the right `organization_id` happens by looking up the
connection via the payload's `phone_number_id`, not via the URL).

## 9.3 Inbound message pipeline

### Step 1 — Webhook verification (one-time, per Meta App)
```
GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
   → compare hub.verify_token to the stored token; echo hub.challenge if it matches
```

### Step 2 — Receiving events (every message/status update)
```
POST /webhooks/whatsapp
Headers: X-Hub-Signature-256: sha256=<hmac>

1. Read the raw request body (before any JSON parsing — signature is over raw bytes)
2. Compute HMAC-SHA256(app_secret, raw_body); compare to the header (constant-time)
   → 401 if mismatched (protects against forged webhook calls)
3. Parse the payload; for each entry → change → value:
     - value.messages[]        → inbound customer messages
     - value.statuses[]        → delivery/read/failed status updates for our outbound messages
     - value.contacts[]        → profile info (name) accompanying messages
4. Resolve the organization via value.metadata.phone_number_id
   → lookup whatsapp_connections WHERE phone_number_id = ...
5. Persist the raw payload (append-only audit trail) and enqueue ONE
   Celery task per message/status with the minimal payload needed
6. Return 200 OK immediately (target: < 2s, well within Meta's ~20s timeout —
   acking fast prevents Meta from retrying and double-delivering)
```

**Idempotency is critical**: Meta retries deliveries on timeout/5xx. The
`messages` table has a unique partial index on
`(organization_id, whatsapp_message_id)` (migration 04); the ingestion task
upserts on conflict and is safe to run twice for the same message.

### Step 3 — Processing a message (`process_inbound_whatsapp_message`, Celery)
```
1. Upsert contact  (organization_id, whatsapp_phone) — capture profile name on first contact
2. Upsert conversation (organization_id, contact_id) — reopen if 'closed', bump last_message_at
3. Insert message (direction='inbound', sender_type='contact', whatsapp_message_id, content/media_url)
4. Mark the inbound message as read via Graph API (POST /{phone_number_id}/messages
   { status: "read", message_id })
5. If conversation.ai_enabled is false → stop here (human-owned thread; agents
   see it in their inbox and reply manually via POST /conversations/{id}/messages)
6. Else → hand off to the AI reply pipeline (next section)
```

### Step 4 — AI reply generation (still within the same task, or a chained one)
```
1. Load recent conversation history (last N messages)
2. RAG retrieval: embed the inbound message, pgvector cosine search over
   knowledge_base_chunks scoped to organization_id, top-K chunks
3. Assemble the prompt: agent persona + qualification-field instructions +
   retrieved context + conversation history + the new message
4. Call the configured provider (OpenAI or Anthropic) via orchestrator.generate_reply()
5. Parse structured output:
     - reply_text            → what to send back
     - extracted_fields      → { name?, phone?, email?, budget?, location? }
     - detected_intent       → { wants_to_book?: bool, handoff_requested?: bool, ... }
6. Log the call to ai_interactions (tokens, cost, latency, retrieved chunk IDs)
7. Side effects:
     - extracted_fields present → crm_service.upsert_lead_from_conversation(...)
       (creates/updates `leads`, writes a `lead_activities` row)
     - wants_to_book           → calendar_service proposes slots in the reply
       (may take an extra LLM round-trip to confirm a specific slot)
     - handoff_requested OR low-confidence response → flips
       conversation.ai_enabled = false, assigned_agent_type = 'human',
       notifies the team (in-app + optional email)
8. Send the reply via whatsapp_client.send_text(...) (next section)
```

## 9.4 Outbound message pipeline

`whatsapp_client.py` wraps the Graph API `/​{phone_number_id}/messages`
endpoint with:

- **Decryption** of the stored access token at call time (never logged, never
  cached in plaintext beyond the request scope).
- **Typed senders**: `send_text`, `send_template`, `send_interactive` (quick
  replies/buttons for things like slot selection), `send_media`.
- **24-hour session window awareness**: free-form messages can only be sent
  within 24h of the customer's last message; outside that window the client
  must use a pre-approved **template message**. The orchestrator checks
  `conversations.last_message_at` and falls back to a template (e.g. a
  follow-up template) automatically when outside the window — this is also
  *why* `whatsapp/sync-templates` exists (Phase 6 depends on approved
  templates for follow-ups that fire after 24h of silence).
- **Retries with backoff** (`tenacity`) on transient 5xx/timeout responses;
  permanent 4xx (e.g. invalid number) marks the message `failed` and surfaces
  it in the inbox rather than retrying forever.
- **Rate limiting**: per-organization outbound rate limiter (Redis token
  bucket) to stay within Meta's per-number messaging limits and to cap
  AI-driven send volume as a cost/abuse safeguard.

```
Send request (from AI pipeline, manual reply, or follow-up step)
        │
        ▼
whatsapp_client.send_*(...)
   1. Acquire org rate-limit token (Redis)
   2. Decrypt access token; build Graph API request
   3. POST https://graph.facebook.com/v{version}/{phone_number_id}/messages
   4. On success: insert `messages` row (direction='outbound',
      sender_type='ai_agent'|'human_agent'|'system', status='sent',
      whatsapp_message_id = response.messages[0].id)
   5. On failure: insert `messages` row with status='failed' + reason in ai_metadata;
      raise ExternalServiceError for the caller to handle (retry/notify)
```

### Delivery status updates
Meta posts `statuses[]` webhook events (`sent` → `delivered` → `read`, or
`failed`) keyed by `whatsapp_message_id`. The ingestion path (§9.3 step 2)
routes these to a lightweight handler that updates the matching `messages.status`
— purely a status-column update, no conversation/AI processing triggered.

## 9.5 Media handling

Inbound media (images, documents, audio, video sent by customers):
1. Webhook payload contains a Meta `media_id`.
2. Worker calls `GET /{media_id}` to obtain a short-lived CDN URL, downloads
   the file, and re-uploads it to Supabase Storage (Meta's URLs expire —
   never store them directly).
3. `messages.media_url` points at our Storage object; `message_type` reflects
   the media kind.

Outbound media (e.g. business sending a brochure/photo): uploaded to Meta via
`POST /{phone_number_id}/media` first, then referenced by the returned
`media_id` in the send request.

## 9.6 Failure handling & resilience matrix

| Failure | Handling |
|---|---|
| Webhook signature invalid | `401`, log + alert (possible spoofing attempt) |
| Duplicate delivery (retry) | Upsert on `(organization_id, whatsapp_message_id)` — no-op |
| Graph API 5xx / timeout on send | Retry with exponential backoff (`tenacity`, max 3 attempts); mark `failed` after exhaustion |
| Graph API 4xx on send (bad number, re-engagement window expired) | No retry; mark `failed`, surface reason in the inbox, suggest a template |
| LLM provider outage/timeout | Circuit breaker trips after N consecutive failures; send a graceful fallback message ("We'll get back to you shortly") and flip the conversation to human-owned |
| Access token expired/revoked | Connection status → `error`; admin notified to reconnect; sends/receives pause gracefully (inbound is still stored, just not auto-replied) |
| Webhook endpoint downtime | Meta retries for up to ~7 days with backoff; once back up, the idempotent pipeline catches up without data loss |

## 9.7 Testing & sandbox strategy

- Meta provides **test WhatsApp Business numbers** in the developer console —
  used for end-to-end testing without a live business number.
- `ngrok`/Cloudflare Tunnel exposes the local FastAPI webhook during
  development; staging gets a stable HTTPS URL on the container platform.
- Recorded payload fixtures (text, image, status-update, error events) drive
  the contract tests referenced in `06-fastapi-backend-architecture.md §6.10`,
  so the parsing/ingestion logic is verified without depending on live Meta
  availability.
- The `/agents/{id}/test` sandbox endpoint exercises the AI reply pipeline
  end-to-end (RAG + LLM + structured parsing) without sending a real WhatsApp
  message — used for prompt iteration and pre-launch QA.
