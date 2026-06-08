-- =============================================================================
-- WhatsAgent AI — Migration 10: Analytics rollups & audit log
-- =============================================================================

-- -----------------------------------------------------------------------------
-- analytics_daily_stats: pre-aggregated per-org/per-day metrics for fast
-- dashboard reads (populated by the refresh_analytics_daily_stats worker)
-- -----------------------------------------------------------------------------
create table public.analytics_daily_stats (
  id                            uuid primary key default gen_random_uuid(),
  organization_id               uuid not null references public.organizations (id) on delete cascade,
  date                          date not null,
  conversations_count           integer not null default 0,
  new_leads_count               integer not null default 0,
  appointments_booked_count     integer not null default 0,
  ai_messages_sent              integer not null default 0,
  ai_messages_total             integer not null default 0,
  human_handoffs_count          integer not null default 0,
  created_at                    timestamptz not null default now(),
  updated_at                    timestamptz not null default now(),
  constraint analytics_daily_stats_org_date_unique unique (organization_id, date)
);

create index idx_analytics_daily_stats_org_date on public.analytics_daily_stats (organization_id, date desc);

create trigger trg_analytics_daily_stats_updated_at
  before update on public.analytics_daily_stats
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- audit_logs: append-only record of sensitive actions (connections, roles, …)
-- -----------------------------------------------------------------------------
create table public.audit_logs (
  id                uuid primary key default gen_random_uuid(),
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  actor_id          uuid references public.profiles (id) on delete set null,
  action            text not null,
  entity_type       text,
  entity_id         uuid,
  metadata          jsonb not null default '{}'::jsonb,
  created_at        timestamptz not null default now()
);

create index idx_audit_logs_org_created on public.audit_logs (organization_id, created_at desc);
