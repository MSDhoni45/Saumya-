-- Operator alerting (P0.2).
--
-- When the automated pipeline cannot finish a turn (WhatsApp send failure,
-- terminal status transition like `failed`), there must be an operator-visible
-- record so a human can intervene. Existing system messages live in the
-- conversation thread; alerts are a separate, ack-able inbox.
--
-- RLS policies mirror `ai_interactions` exactly — see migration 20260608140001.
-- Direct asyncpg connections from the app bypass RLS (postgres role), but the
-- policies guard any future JWT/PostgREST access path.

do $$
begin
  if not exists (select 1 from pg_tables where tablename = 'operator_alerts') then
    create table operator_alerts (
      id uuid primary key default gen_random_uuid(),
      business_id uuid not null references businesses(id) on delete cascade,
      conversation_id uuid references conversations(id) on delete set null,
      message_id uuid references messages(id) on delete set null,
      kind text not null,
      severity text not null,
      title text not null,
      body text not null,
      created_at timestamptz not null default now(),
      acknowledged_at timestamptz,
      acknowledged_by uuid references users(id) on delete set null
    );
  end if;
end $$;

-- Hot path: list unacknowledged alerts for a business, newest first.
create index if not exists ix_operator_alerts_business_unack
  on operator_alerts (business_id, acknowledged_at, created_at desc);

alter table operator_alerts enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
     where tablename = 'operator_alerts' and policyname = 'operator_alerts_select'
  ) then
    create policy operator_alerts_select on operator_alerts
      for select using (business_id = auth_business_id());
  end if;

  if not exists (
    select 1 from pg_policies
     where tablename = 'operator_alerts' and policyname = 'operator_alerts_insert'
  ) then
    create policy operator_alerts_insert on operator_alerts
      for insert with check (business_id = auth_business_id());
  end if;

  if not exists (
    select 1 from pg_policies
     where tablename = 'operator_alerts' and policyname = 'operator_alerts_update'
  ) then
    create policy operator_alerts_update on operator_alerts
      for update using (business_id = auth_business_id())
      with check (business_id = auth_business_id());
  end if;
end $$;
