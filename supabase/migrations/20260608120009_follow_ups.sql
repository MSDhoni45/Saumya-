-- =============================================================================
-- WhatsAgent AI — Migration 09: Follow-up agent (sequences, steps, enrollments)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- follow_up_sequences: a named, triggerable nurture sequence
-- -----------------------------------------------------------------------------
create table public.follow_up_sequences (
  id                uuid primary key default gen_random_uuid(),
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  name              text not null,
  trigger           public.follow_up_trigger not null default 'manual',
  is_active         boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index idx_follow_up_sequences_org on public.follow_up_sequences (organization_id);
create index idx_follow_up_sequences_org_active on public.follow_up_sequences (organization_id, is_active);

create trigger trg_follow_up_sequences_updated_at
  before update on public.follow_up_sequences
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- follow_up_steps: ordered messages within a sequence
-- -----------------------------------------------------------------------------
create table public.follow_up_steps (
  id                  uuid primary key default gen_random_uuid(),
  sequence_id         uuid not null references public.follow_up_sequences (id) on delete cascade,
  step_order          integer not null,
  delay_minutes       integer not null default 0,
  message_template    text not null,
  channel             public.follow_up_channel not null default 'whatsapp',
  created_at          timestamptz not null default now(),
  constraint follow_up_steps_sequence_order_unique unique (sequence_id, step_order),
  constraint follow_up_steps_delay_non_negative check (delay_minutes >= 0),
  constraint follow_up_steps_order_positive check (step_order >= 1)
);

create index idx_follow_up_steps_sequence_order on public.follow_up_steps (sequence_id, step_order);

-- -----------------------------------------------------------------------------
-- follow_up_enrollments: a lead's progress through a sequence
--
-- organization_id is denormalized here (mirroring messages/lead_activities)
-- to keep RLS scoping and dashboard queries simple and index-friendly.
-- -----------------------------------------------------------------------------
create table public.follow_up_enrollments (
  id                  uuid primary key default gen_random_uuid(),
  organization_id     uuid not null references public.organizations (id) on delete cascade,
  sequence_id         uuid not null references public.follow_up_sequences (id) on delete cascade,
  lead_id             uuid not null references public.leads (id) on delete cascade,
  contact_id          uuid not null references public.contacts (id) on delete cascade,
  current_step        integer not null default 0,
  status              public.enrollment_status not null default 'active',
  next_run_at         timestamptz,
  enrolled_at         timestamptz not null default now(),
  completed_at        timestamptz,
  constraint follow_up_enrollments_sequence_lead_unique unique (sequence_id, lead_id),
  constraint follow_up_enrollments_current_step_non_negative check (current_step >= 0)
);

create index idx_follow_up_enrollments_org on public.follow_up_enrollments (organization_id);
create index idx_follow_up_enrollments_lead on public.follow_up_enrollments (lead_id);

-- The scheduler worker polls exactly this shape: active enrollments due to run.
create index idx_follow_up_enrollments_due
  on public.follow_up_enrollments (next_run_at)
  where status = 'active';
