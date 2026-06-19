-- X Automation v2: DM tracking + auto-DM config + webhook reply storage
-- Safe to run multiple times (IF NOT EXISTS / IF EXISTS guards).

-- ── x_outreach: expand status CHECK to include 'dm_sent' ───────────────────
ALTER TABLE public.x_outreach
  DROP CONSTRAINT IF EXISTS x_outreach_status_check;

ALTER TABLE public.x_outreach
  ADD CONSTRAINT x_outreach_status_check
  CHECK (status IN ('pending','reviewed','sent','dm_sent','replied','converted','skipped'));

-- ── x_lead_searches: auto-DM configuration ──────────────────────────────────
ALTER TABLE public.x_lead_searches
  ADD COLUMN IF NOT EXISTS auto_dm_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS auto_dm_threshold INTEGER NOT NULL DEFAULT 70;

COMMENT ON COLUMN public.x_lead_searches.auto_dm_enabled
  IS 'When true the auto_send_dms Celery task will DM matching prospects.';
COMMENT ON COLUMN public.x_lead_searches.auto_dm_threshold
  IS 'Minimum AI score (0-100) required for a prospect to receive an auto-DM.';

-- ── x_outreach: DM delivery + reply tracking ────────────────────────────────
ALTER TABLE public.x_outreach
  ADD COLUMN IF NOT EXISTS dm_message_id TEXT,
  ADD COLUMN IF NOT EXISTS dm_sent_at    TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS reply_text    TEXT,
  ADD COLUMN IF NOT EXISTS replied_at    TIMESTAMPTZ;

COMMENT ON COLUMN public.x_outreach.dm_message_id
  IS 'X DM event ID returned by the DM send API.';
COMMENT ON COLUMN public.x_outreach.dm_sent_at
  IS 'When the auto (or manual) DM was delivered.';
COMMENT ON COLUMN public.x_outreach.reply_text
  IS 'Text of the prospect''s reply DM, captured via X Activity webhook.';
COMMENT ON COLUMN public.x_outreach.replied_at
  IS 'Timestamp of the prospect''s reply DM.';
