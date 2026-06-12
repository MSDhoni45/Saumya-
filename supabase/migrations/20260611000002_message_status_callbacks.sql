-- Meta WhatsApp Cloud API status callbacks (sent / delivered / read / failed).
--
-- Prior state: `messages.status` advanced once at send time and was never updated
-- from Meta's callbacks — `value.statuses` payloads were silently dropped by the
-- webhook dispatcher. That left delivery analytics, read-receipt UI, and failure
-- surfacing all blind.
--
-- This migration adds the per-status timestamp columns plus error metadata so
-- the service layer can record the full lifecycle of every outbound message.
-- The pre-existing `status` CHECK constraint already permits the full set
-- (queued, sent, delivered, read, failed) so no constraint change is needed.

alter table messages
  add column if not exists delivered_at timestamptz,
  add column if not exists read_at      timestamptz,
  add column if not exists failed_at    timestamptz,
  add column if not exists error_code   text,
  add column if not exists error_title  text;

-- Status filter on listing endpoints (apps/api/app/api/v1/whatsapp.py) currently
-- runs a sequential scan per business; this index makes it index-only for the
-- common dashboard query (recent failed/delivered for a business).
create index if not exists ix_messages_business_status
  on messages (business_id, status);
