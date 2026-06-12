-- Outbound idempotency for AI replies (P0.4).
--
-- Prior state: nothing prevented two `ai_interactions` rows from sharing the
-- same `inbound_message_id`. If a Celery task partially succeeded (LLM ran,
-- WhatsApp send went out) and then a downstream DB commit failed, the retry
-- would re-run the whole turn, producing a second LLM call and a second
-- WhatsApp message for the same inbound — visible duplicate replies to the
-- contact and double-counted usage.
--
-- This migration enforces "one inbound → at most one AI reply" at the schema
-- level. The application layer reserves an `ai_interactions` row up-front via
-- INSERT ... ON CONFLICT DO NOTHING; the constraint here is what makes that
-- reservation race-safe.
--
-- Step 1 dedupes any pre-existing duplicate rows by keeping the earliest
-- (MIN(id)) per inbound_message_id. NULL inbound_message_ids are left alone
-- — they exist for sandbox / test interactions where no real inbound message
-- exists, and the unique constraint allows multiple NULLs (Postgres treats
-- NULL as distinct in unique indexes by default).

-- Step 1: dedupe existing rows. Idempotent — no-op when no duplicates exist.
with dupes as (
  select inbound_message_id, min(id) as keep_id
    from ai_interactions
   where inbound_message_id is not null
   group by inbound_message_id
   having count(*) > 1
)
delete from ai_interactions ai
 using dupes
 where ai.inbound_message_id = dupes.inbound_message_id
   and ai.id <> dupes.keep_id;

-- Step 2: enforce uniqueness. Wrapped in a DO block so re-running the
-- migration is a no-op once the constraint exists.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'ux_ai_interactions_inbound_message_id'
  ) then
    alter table ai_interactions
      add constraint ux_ai_interactions_inbound_message_id
      unique (inbound_message_id);
  end if;
end $$;
