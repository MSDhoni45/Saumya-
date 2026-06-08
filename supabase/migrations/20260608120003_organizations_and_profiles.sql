-- =============================================================================
-- WhatsAgent AI — Migration 03: Organizations, profiles, membership
-- =============================================================================

-- -----------------------------------------------------------------------------
-- organizations: the tenant (the business using WhatsAgent AI)
-- -----------------------------------------------------------------------------
create table public.organizations (
  id                    uuid primary key default gen_random_uuid(),
  name                  text not null,
  slug                  text not null unique,
  industry              text,
  timezone              text not null default 'UTC',
  subscription_plan     public.organization_plan not null default 'trial',
  subscription_status   public.subscription_status not null default 'active',
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint organizations_slug_format check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);

create trigger trg_organizations_updated_at
  before update on public.organizations
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- profiles: 1:1 extension of auth.users (display data, not auth data)
-- -----------------------------------------------------------------------------
create table public.profiles (
  id            uuid primary key references auth.users (id) on delete cascade,
  full_name     text,
  avatar_url    text,
  phone         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create trigger trg_profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- Auto-create a profile row whenever a new auth user is created.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, avatar_url)
  values (
    new.id,
    new.raw_user_meta_data ->> 'full_name',
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger trg_create_profile_on_signup
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();

-- -----------------------------------------------------------------------------
-- organization_members: which users belong to which orgs, with what role
-- -----------------------------------------------------------------------------
create table public.organization_members (
  id                uuid primary key default gen_random_uuid(),
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  user_id           uuid references public.profiles (id) on delete cascade,
  role              public.member_role not null default 'agent',
  invited_email     text,
  status            public.member_status not null default 'invited',
  created_at        timestamptz not null default now(),
  constraint organization_members_user_or_invite check (
    user_id is not null or invited_email is not null
  ),
  constraint organization_members_org_user_unique unique (organization_id, user_id)
);

create index idx_org_members_org on public.organization_members (organization_id);
create index idx_org_members_user on public.organization_members (user_id);

-- Prevent duplicate pending invites for the same email within an org
create unique index idx_org_members_unique_pending_invite
  on public.organization_members (organization_id, invited_email)
  where invited_email is not null and status = 'invited';
