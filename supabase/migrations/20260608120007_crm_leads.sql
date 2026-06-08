-- =============================================================================
-- WhatsAgent AI — Migration 07: CRM (leads & activity timeline)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- leads: a contact moving through the sales pipeline
-- -----------------------------------------------------------------------------
create table public.leads (
  id                  uuid primary key default gen_random_uuid(),
  organization_id     uuid not null references public.organizations (id) on delete cascade,
  contact_id          uuid not null references public.contacts (id) on delete cascade,
  stage               public.lead_stage not null default 'new',
  name                text,
  phone               text,
  email               text,
  budget              text,
  location            text,
  source              public.lead_source not null default 'whatsapp',
  assigned_to         uuid references public.profiles (id) on delete set null,
  score               integer,
  notes               text,
  stage_changed_at    timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint leads_org_contact_unique unique (organization_id, contact_id),
  constraint leads_score_range check (score is null or (score >= 0 and score <= 100))
);

create index idx_leads_org_stage on public.leads (organization_id, stage);
create index idx_leads_assigned on public.leads (assigned_to);
create index idx_leads_org_created on public.leads (organization_id, created_at desc);

create trigger trg_leads_updated_at
  before update on public.leads
  for each row execute function public.set_updated_at();

-- Track stage transitions automatically (stamps stage_changed_at, and the
-- application layer additionally writes a matching lead_activities row).
create or replace function public.touch_lead_stage_changed_at()
returns trigger
language plpgsql
as $$
begin
  if new.stage is distinct from old.stage then
    new.stage_changed_at = now();
  end if;
  return new;
end;
$$;

create trigger trg_leads_stage_changed_at
  before update on public.leads
  for each row execute function public.touch_lead_stage_changed_at();

-- -----------------------------------------------------------------------------
-- lead_activities: timeline/audit trail per lead (notes, stage changes, …)
-- -----------------------------------------------------------------------------
create table public.lead_activities (
  id                uuid primary key default gen_random_uuid(),
  lead_id           uuid not null references public.leads (id) on delete cascade,
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  activity_type     public.lead_activity_type not null,
  description       text,
  metadata          jsonb not null default '{}'::jsonb,
  created_by        uuid references public.profiles (id) on delete set null,
  created_at        timestamptz not null default now()
);

create index idx_lead_activities_lead_created on public.lead_activities (lead_id, created_at desc);
create index idx_lead_activities_org on public.lead_activities (organization_id);
