-- businesses --------------------------------------------------------------
-- The tenant entity. Every other table is scoped to a business_id.
create table if not exists businesses (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  industry      text,
  timezone      text not null default 'UTC',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create trigger trg_businesses_set_updated_at
  before update on businesses
  for each row execute function set_updated_at();

-- users ---------------------------------------------------------------------
-- 1:1 with auth.users; adds product-level profile, business membership, and role.
-- Single business_id keeps the model simple (one business per user) — matches
-- the requested table set (no separate membership/join table).
create table if not exists users (
  id            uuid primary key references auth.users (id) on delete cascade,
  business_id   uuid references businesses (id) on delete set null,
  email         text not null,
  full_name     text,
  avatar_url    text,
  role          text not null default 'owner'
                  check (role in ('owner', 'admin', 'agent')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists ix_users_business_id on users (business_id);
create unique index if not exists ux_users_email on users (lower(email));

create trigger trg_users_set_updated_at
  before update on users
  for each row execute function set_updated_at();

-- Auto-provision a `users` row whenever a new Supabase auth user signs up.
create or replace function handle_new_auth_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.users (id, email, full_name)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data ->> 'full_name'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists trg_on_auth_user_created on auth.users;
create trigger trg_on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_auth_user();
