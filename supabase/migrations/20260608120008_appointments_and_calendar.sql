-- =============================================================================
-- WhatsAgent AI — Migration 08: Calendar connection & appointment booking
-- =============================================================================

-- -----------------------------------------------------------------------------
-- calendar_connections: Google Calendar OAuth connection per org (MVP: one)
-- -----------------------------------------------------------------------------
create table public.calendar_connections (
  id                          uuid primary key default gen_random_uuid(),
  organization_id             uuid not null unique references public.organizations (id) on delete cascade,
  provider                    public.calendar_provider not null default 'google',
  google_account_email        text,
  access_token_encrypted      bytea,
  refresh_token_encrypted     bytea,
  calendar_id                 text,
  status                      public.connection_status not null default 'disconnected',
  connected_at                timestamptz,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now()
);

create trigger trg_calendar_connections_updated_at
  before update on public.calendar_connections
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- appointments: bookings created by the AI agent or manually by the team
-- -----------------------------------------------------------------------------
create table public.appointments (
  id                uuid primary key default gen_random_uuid(),
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  lead_id           uuid references public.leads (id) on delete set null,
  contact_id        uuid not null references public.contacts (id) on delete cascade,
  title             text not null,
  starts_at         timestamptz not null,
  ends_at           timestamptz not null,
  timezone          text not null default 'UTC',
  status            public.appointment_status not null default 'scheduled',
  calendar_event_id text,
  location          text,
  meeting_link      text,
  created_via       public.creation_source not null default 'ai_agent',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint appointments_time_range_check check (ends_at > starts_at)
);

create index idx_appointments_org_starts on public.appointments (organization_id, starts_at);
create index idx_appointments_lead on public.appointments (lead_id);
create index idx_appointments_contact on public.appointments (contact_id);
create index idx_appointments_org_status on public.appointments (organization_id, status);

create trigger trg_appointments_updated_at
  before update on public.appointments
  for each row execute function public.set_updated_at();
