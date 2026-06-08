create table if not exists followup_sequences (
  id              uuid primary key default gen_random_uuid(),
  business_id     uuid not null references businesses (id) on delete cascade,
  name            text not null,
  trigger_event   text not null
                    check (trigger_event in ('lead_created', 'no_response', 'appointment_no_show', 'manual')),
  -- Ordered list of steps, e.g.
  --   [{"delay_hours": 24, "channel": "whatsapp", "template": "follow_up_1"}, ...]
  steps           jsonb not null default '[]'::jsonb,
  is_active       boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists ix_followup_sequences_business_id on followup_sequences (business_id);
create index if not exists ix_followup_sequences_business_active on followup_sequences (business_id, is_active);

create trigger trg_followup_sequences_set_updated_at
  before update on followup_sequences
  for each row execute function set_updated_at();
