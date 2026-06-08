-- leads -----------------------------------------------------------------------
create table if not exists leads (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid not null references businesses (id) on delete cascade,
  conversation_id     uuid references conversations (id) on delete set null,
  assigned_user_id    uuid references users (id) on delete set null,
  name                text,
  phone               text,
  email               text,
  stage               text not null default 'new'
                        check (stage in ('new', 'contacted', 'qualified', 'proposal', 'won', 'lost')),
  source              text not null default 'whatsapp',
  notes               text,
  stage_changed_at    timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists ix_leads_business_id on leads (business_id);
create index if not exists ix_leads_business_stage on leads (business_id, stage);
create index if not exists ix_leads_conversation_id on leads (conversation_id);
create index if not exists ix_leads_assigned_user_id on leads (assigned_user_id);

-- Track stage transitions (for funnel/conversion analytics) and keep `updated_at` fresh.
create or replace function touch_lead_stage_changed_at()
returns trigger
language plpgsql
as $$
begin
  if new.stage is distinct from old.stage then
    new.stage_changed_at = now();
  end if;
  new.updated_at = now();
  return new;
end;
$$;

create trigger trg_leads_set_updated_at
  before update on leads
  for each row execute function touch_lead_stage_changed_at();

-- appointments ------------------------------------------------------------------
create table if not exists appointments (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid not null references businesses (id) on delete cascade,
  lead_id             uuid references leads (id) on delete set null,
  conversation_id     uuid references conversations (id) on delete set null,
  title               text not null,
  scheduled_at        timestamptz not null,
  duration_minutes    integer not null default 30 check (duration_minutes > 0),
  status              text not null default 'scheduled'
                        check (status in ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
  location            text,
  notes               text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists ix_appointments_business_id on appointments (business_id);
create index if not exists ix_appointments_business_scheduled on appointments (business_id, scheduled_at);
create index if not exists ix_appointments_lead_id on appointments (lead_id);
create index if not exists ix_appointments_business_status on appointments (business_id, status);

create trigger trg_appointments_set_updated_at
  before update on appointments
  for each row execute function set_updated_at();
