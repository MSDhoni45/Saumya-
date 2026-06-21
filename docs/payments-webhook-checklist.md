# Payments webhook checklist (Stripe + Razorpay)

`BILLING_ENABLED=false` is the current master switch. Subscriptions are flipped
manually via `POST /api/v1/admin/businesses/{id}/activate`. Before flipping
`BILLING_ENABLED=true`, work through every box in this file — a misconfigured
webhook receiver is the single biggest revenue-loss bug class in SaaS billing.

## Signature verification (must-have, blocking)

- [ ] **Stripe**: handler verifies `Stripe-Signature` against
  `STRIPE_WEBHOOK_SECRET` using the Stripe SDK's
  `Webhook.construct_event(payload, sig_header, secret)` — never roll your
  own HMAC. The library handles timestamp tolerance + double-key rotation.
- [ ] **Razorpay**: handler verifies `X-Razorpay-Signature` using
  `razorpay.utility.verify_webhook_signature(payload, sig, secret)`.
  Reject any request that fails verification with HTTP 400 *before* parsing
  the body — do not log the body on failure (it can contain card metadata).
- [ ] Raw request body is captured **before** any middleware deserialises
  JSON. FastAPI's `await request.body()` must run before the route reads
  `request.json()`, otherwise the body bytes get consumed and signature
  verification fails.
- [ ] Webhook secret is fetched from Secrets Manager at startup, not from a
  baked-in env in the container image.
- [ ] Constant-time comparison only (SDK enforces; do not pattern-match by
  hand and break this).

## Idempotency

- [ ] Every webhook handler is keyed by the processor's event id
  (`event.id` for Stripe, `payload.payload.payment.entity.id` for Razorpay)
  and stored in a `processed_billing_events(event_id PRIMARY KEY, ...)` row
  inside the same DB transaction that mutates `subscriptions`.
- [ ] Duplicate delivery (Stripe retries on 5xx for up to 3 days) returns
  HTTP 200 immediately after the dedupe check — never re-applies the side
  effect.

## Retries + ordering

- [ ] Handler returns HTTP 200 only after the DB commit succeeds. Returning
  200 + crashing mid-write loses the event silently.
- [ ] Handler is tolerant of out-of-order delivery
  (`invoice.payment_succeeded` may arrive before `customer.subscription.updated`).
  Reconcile against the processor's authoritative state with a per-customer
  `Subscriptions.retrieve()` on every webhook, not just the delta in the
  payload.
- [ ] Long-running side effects (sending emails, posting to Slack) are
  off-loaded to Celery — keep the webhook hot path <500ms.

## Replay + observability

- [ ] All webhook events (raw payload + verification result + outcome) are
  written to `billing_events` so an operator can replay any range from the
  admin console. Retention >= 90 days.
- [ ] Sentry captures any exception inside the webhook handler with the
  processor + event_id in the tags, never the body (PII).
- [ ] CloudWatch alarm wired on `level=ERROR` log lines that contain
  `webhook` (the existing `infra/cloudwatch/alarms.sh` filter is generic; add
  a per-handler one once volume warrants).

## Security hardening

- [ ] Webhook URL is hard to guess (e.g. `/api/v1/billing/webhook/stripe/{token}`
  where `{token}` is a long random in env). Signature verification is the
  primary gate; this is defence-in-depth against probing.
- [ ] Receiver is allow-listed to Stripe / Razorpay outbound IP ranges at
  the ALB or WAF if the processor publishes them.
- [ ] Webhook endpoint is **not** rate-limited at the IP layer — Stripe
  retries from a small pool and would get throttled. Rely on the signature
  gate + idempotency table instead.
- [ ] Test events from the Stripe / Razorpay dashboards are routed to the
  staging stack, never prod. Use distinct webhook secrets per environment.

## Pre-flip dry run

Before setting `BILLING_ENABLED=true` in prod:

1. Enable in staging. Send each Stripe test event
   (`stripe trigger checkout.session.completed`,
   `customer.subscription.updated`, `invoice.payment_failed`,
   `customer.subscription.deleted`) and verify the resulting
   `subscriptions` row.
2. Run a Razorpay test payment in `test` mode and confirm the
   `subscription.activated` webhook arrives + applies.
3. Replay every staged event from `billing_events` and confirm idempotency
   table rejects duplicates (HTTP 200, no row changes).
4. Page the on-call by tripping one ERROR-level log line and confirm the
   alarm fires.

Only after all four pass does prod get the flip.
